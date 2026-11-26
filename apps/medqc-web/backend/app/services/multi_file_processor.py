"""
多文件处理服务
从 drg 项目迁移并适配 medqc 项目。
支持 ZIP 解压、多 Excel 文件探索和数据合并清洗。
"""
import os
from pathlib import Path
import uuid
import zipfile
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
import re

# ZIP 安全解压限制（防 Zip Slip / Zip Bomb / 同名覆盖）
MAX_ZIP_ENTRIES = int(os.getenv("SMART_UPLOAD_MAX_ZIP_ENTRIES", "100"))
MAX_ZIP_SINGLE_FILE_BYTES = int(
    os.getenv("SMART_UPLOAD_MAX_ZIP_SINGLE_FILE_BYTES", str(50 * 1024 * 1024))
)
MAX_ZIP_TOTAL_BYTES = int(
    os.getenv("SMART_UPLOAD_MAX_ZIP_TOTAL_BYTES", str(100 * 1024 * 1024))
)
_ZIP_STREAM_CHUNK_BYTES = 64 * 1024
_UNIX_SYMLINK_MODE = 0o120000
_UNIX_FILE_TYPE_MASK = 0o170000

# 核心字段定义（DIP/DRG 分析必需）- 扩展别名列表
CORE_COLUMNS = {
    # 基础标识
    "case_id": ["结算id", "病例ID", "病案号", "住院号", "就诊号"],
    "patient_name": ["人员姓名", "患者姓名", "姓名"],
    "patient_code": ["人员编码", "患者编码"],
    
    # 分组信息
    "dip_code": ["分组编码", "DIP病种编码", "病种编码"],
    "dip_name": ["分组名称", "DIP病种名称", "病种名称"],
    "dip_weight": ["分组病种分值", "DIP点数", "病种分值", "点数", "实际结算分值"],
    "actual_weight": ["实际结算分值", "实际分值"],
    
    # 费用信息
    "total_cost": ["住院医疗总费用", "实际费用", "总费用", "住院费用", "医疗总费用"],
    "dip_payment": ["DIP支付标准", "支付标准", "医保支付", "统筹支出", "DIP统筹支付总金额"],
    "profit_loss": ["盈亏额", "盈亏", "盈亏金额", "结余"],
    
    # 科室和医生
    "department": ["出院科室名称", "科室名称", "出院科室", "科室", "住院科室"],
    "doctor": ["主诊医师姓名", "主治医师", "医师姓名", "主管医生"],
    
    # 住院信息
    "los": ["实际住院天数", "住院天数", "住院日数"],
    "settle_date": ["结算日期", "出院日期"],
    "admission_date": ["入院日期", "入院时间"],
    "age": ["年龄"],
    "gender": ["性别"],
    
    # 费用明细
    "drug_cost": ["西药费", "药品费", "药费"],
    "treatment_cost": ["治疗费"],
    
    # 医保信息
    "insurance_type": ["险种类型", "医疗类别", "医保类型"],
    "is_remote": ["异地标志", "异地"],
}


class MultiFileProcessor:
    """多文件处理器"""
    
    def __init__(self, upload_dir: str):
        self.upload_dir = upload_dir
        self.files_info: List[Dict] = []
        self.merged_df: Optional[pd.DataFrame] = None
        self.column_mapping: Dict[str, str] = {}
        self.common_columns: List[str] = []
        self.all_columns: List[str] = []
        self.process_log: List[Dict] = []
    
    def log(self, step: str, message: str, status: str = "info"):
        """记录处理日志"""
        self.process_log.append({
            "step": step,
            "message": message,
            "status": status,
            "time": datetime.now().isoformat()
        })
    
    @staticmethod
    def _decode_zip_member_name(file_info: zipfile.ZipInfo) -> str:
        raw_name = file_info.filename or ""
        if file_info.flag_bits & 0x800:
            return raw_name
        try:
            return raw_name.encode("cp437").decode("gbk")
        except Exception:
            return raw_name

    @staticmethod
    def _validate_zip_member_path(member_name: str, file_info: zipfile.ZipInfo) -> list[str]:
        if not member_name or "\x00" in member_name:
            raise ValueError("ZIP 包含非法文件名条目")
        unix_mode = (file_info.external_attr >> 16) & _UNIX_FILE_TYPE_MASK
        if unix_mode == _UNIX_SYMLINK_MODE:
            raise ValueError("ZIP 不允许包含符号链接条目")
        if member_name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", member_name):
            raise ValueError("ZIP 包含非法绝对路径条目")
        normalized = member_name.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part]
        if not parts or any(part in {".", ".."} for part in parts):
            raise ValueError("ZIP 包含非法路径遍历条目")
        return parts

    @staticmethod
    def _sanitize_excel_basename(raw_base: str) -> str:
        cleaned = re.sub(r"[\x00-\x1f\x7f]", "", str(raw_base or "")).strip()
        if not cleaned or cleaned in {".", ".."} or "/" in cleaned or "\\" in cleaned:
            raise ValueError("ZIP 包含非法 Excel 文件名")
        return cleaned

    def extract_zip(
        self,
        zip_path: str,
        extract_dir: str,
        *,
        max_entries: Optional[int] = None,
        max_single_file_bytes: Optional[int] = None,
        max_total_bytes: Optional[int] = None,
    ) -> List[str]:
        """安全解压 ZIP 文件，防 Zip Slip / Zip Bomb / 同名覆盖，返回 Excel 文件列表。"""
        self.log("解压文件", f"正在解压: {os.path.basename(zip_path)}")

        entry_limit = max(1, int(MAX_ZIP_ENTRIES if max_entries is None else max_entries))
        single_limit = max(
            1,
            int(
                MAX_ZIP_SINGLE_FILE_BYTES
                if max_single_file_bytes is None
                else max_single_file_bytes
            ),
        )
        total_limit = max(
            1,
            int(MAX_ZIP_TOTAL_BYTES if max_total_bytes is None else max_total_bytes),
        )

        extract_root = Path(extract_dir).resolve()
        extract_root.mkdir(parents=True, exist_ok=True)

        excel_files: List[str] = []
        used_names: set[str] = set()
        total_extracted = 0
        current_writing_path: Optional[Path] = None

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                infos = zip_ref.infolist()
                if len(infos) > entry_limit:
                    raise ValueError(f"ZIP 文件条目数超过限制（最多 {entry_limit} 个）")

                for file_info in infos:
                    member_name = self._decode_zip_member_name(file_info)
                    parts = self._validate_zip_member_path(member_name, file_info)

                    if file_info.is_dir() or member_name.endswith(("/", "\\")):
                        continue

                    if any(part == "__MACOSX" for part in parts):
                        continue

                    base_name = self._sanitize_excel_basename(parts[-1])
                    if base_name.startswith("._"):
                        continue
                    if not base_name.lower().endswith((".xlsx", ".xls")):
                        continue

                    if file_info.file_size > single_limit:
                        raise ValueError("ZIP 内单文件解压大小超过限制")
                    if total_extracted + file_info.file_size > total_limit:
                        raise ValueError("ZIP 总解压大小超过限制")

                    safe_name = base_name
                    target_path = (extract_root / safe_name).resolve()
                    if safe_name.lower() in used_names or target_path.exists():
                        safe_name = f"{len(excel_files) + 1:03d}_{uuid.uuid4().hex[:6]}_{base_name}"
                        target_path = (extract_root / safe_name).resolve()

                    if not target_path.is_relative_to(extract_root) or target_path == extract_root:
                        raise ValueError("ZIP 目标路径越界")

                    written_for_file = 0
                    current_writing_path = target_path
                    with zip_ref.open(file_info, "r") as src, open(target_path, "wb") as dst:
                        while True:
                            chunk = src.read(_ZIP_STREAM_CHUNK_BYTES)
                            if not chunk:
                                break
                            written_for_file += len(chunk)
                            total_extracted += len(chunk)
                            if written_for_file > single_limit:
                                raise ValueError("ZIP 内单文件解压大小超过限制")
                            if total_extracted > total_limit:
                                raise ValueError("ZIP 总解压大小超过限制")
                            dst.write(chunk)

                    used_names.add(safe_name.lower())
                    excel_files.append(str(target_path))
                    current_writing_path = None
        except Exception:
            for created_path in excel_files:
                try:
                    Path(created_path).unlink(missing_ok=True)
                except OSError:
                    pass
            if (
                current_writing_path is not None
                and current_writing_path.is_relative_to(extract_root)
                and current_writing_path != extract_root
            ):
                try:
                    current_writing_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

        self.log("解压文件", f"发现 {len(excel_files)} 个 Excel 文件", "success")
        return excel_files
    
    def explore_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """探索所有文件结构"""
        self.log("探索数据", "正在分析文件结构...")
        
        self.files_info = []
        all_columns = set()
        common_columns_set = None
        first_file_columns_order: List[str] = []
        
        for file_path in file_paths:
            filename = os.path.basename(file_path)
            
            try:
                sheet_name = self._select_best_sheet(file_path)
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                normalized_columns = [self._normalize_column_name(c) for c in list(df.columns)]
                df.columns = normalized_columns
                df = df.loc[:, ~df.columns.duplicated()]
                
                # 提取月份（从文件名中）
                month = self._extract_month(filename)
                
                file_info = {
                    "filename": filename,
                    "path": file_path,
                    "sheet_name": sheet_name,
                    "rows": len(df),
                    "columns": list(df.columns),
                    "column_count": len(df.columns),
                    "month": month
                }
                
                self.files_info.append(file_info)
                all_columns.update(df.columns)

                cols_set = set(df.columns)
                if common_columns_set is None:
                    common_columns_set = cols_set
                    first_file_columns_order = list(df.columns)
                else:
                    common_columns_set &= cols_set
                
            except Exception as e:
                self.log("探索数据", f"读取 {filename} 失败: {str(e)}", "error")
        
        common_columns_set = common_columns_set or set()
        self.common_columns = [c for c in first_file_columns_order if c in common_columns_set]
        self.all_columns = sorted(list(all_columns))

        # 生成字段映射
        self.column_mapping = self._auto_map_columns(self.all_columns)
        
        summary = {
            "file_count": len(self.files_info),
            "total_rows": sum(f["rows"] for f in self.files_info),
            "all_columns": self.all_columns,
            "common_columns": self.common_columns,
            "common_column_count": len(self.common_columns),
            "files": self.files_info,
            "column_mapping": self.column_mapping,
            "mapped_fields": list(self.column_mapping.keys())
        }
        
        self.log("探索数据", 
                 f"共 {summary['file_count']} 个文件，{summary['total_rows']} 行数据，{len(self.all_columns)} 个字段，交集 {len(self.common_columns)} 个字段",
                 "success")
        
        return summary
    
    def _extract_month(self, filename: str) -> Optional[str]:
        """从文件名提取月份"""
        patterns = [
            r'(\d{4})年.*?(\d{1,2})月',
            r'(\d{4})-(\d{2})',
            r'(\d{1,2})月',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    return f"{groups[0]}-{int(groups[1]):02d}"
                else:
                    return groups[0]
        
        return None
    
    def _auto_map_columns(self, columns: List[str]) -> Dict[str, str]:
        """自动映射列名到标准字段"""
        mapping = {}
        
        for std_field, aliases in CORE_COLUMNS.items():
            for col in columns:
                col_clean = col.strip()
                if col_clean in aliases:
                    mapping[std_field] = col_clean
                    break
        
        return mapping
    
    def merge_files(self, file_paths: List[str] = None, column_mode: str = "union") -> pd.DataFrame:
        """合并多个文件"""
        self.log("数据合并", "正在合并所有文件...")
        
        if file_paths is None:
            file_paths = [f["path"] for f in self.files_info]
        
        all_data = []

        keep_columns = None
        if column_mode == "intersection":
            keep_columns = set(self.common_columns or [])
        elif column_mode != "union":
            raise ValueError("column_mode must be 'union' or 'intersection'")
        
        for file_info in self.files_info:
            file_path = file_info["path"]
            filename = file_info["filename"]
            month = file_info.get("month")
            
            try:
                sheet_name = file_info.get("sheet_name", 0)
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                df.columns = [self._normalize_column_name(c) for c in list(df.columns)]
                df = df.loc[:, ~df.columns.duplicated()]

                if keep_columns is not None:
                    ordered = [c for c in (self.common_columns or []) if c in df.columns]
                    df = df[ordered]
                
                # 添加月份列
                if month:
                    df["数据月份"] = month
                else:
                    df["数据月份"] = filename
                
                # 添加来源文件
                df["来源文件"] = filename
                
                all_data.append(df)
                
            except Exception as e:
                self.log("数据合并", f"合并 {filename} 失败: {str(e)}", "error")
        
        # 合并所有数据
        self.merged_df = pd.concat(all_data, ignore_index=True, sort=False)
        
        self.log("数据合并", f"合并完成，共 {len(self.merged_df)} 行", "success")
        
        return self.merged_df
    
    def clean_data(self) -> pd.DataFrame:
        """清洗数据 - 保留原始列名，让 FieldMapper/LLM 处理映射"""
        if self.merged_df is None:
            raise ValueError("请先合并数据")
        
        self.log("数据清洗", "正在清洗数据...")
        
        df = self.merged_df.copy()
        original_rows = len(df)
        
        # 1. 删除完全重复的行
        df = df.drop_duplicates()
        dup_removed = original_rows - len(df)
        
        # 2. 处理常见数值字段（使用原始中文列名）
        numeric_field_patterns = ["费用", "费", "支出", "支付", "金额", "点数", "分值", "天数", "年龄"]
        for col in df.columns:
            if any(p in col for p in numeric_field_patterns):
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 3. 处理日期字段（使用原始中文列名）
        date_field_patterns = ["日期", "时间"]
        for col in df.columns:
            if any(p in col for p in date_field_patterns):
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        self.merged_df = df
        
        self.log("数据清洗", 
                 f"删除重复 {dup_removed} 行，剩余 {len(df)} 行",
                 "success")
        
        return df
    
    def get_process_log(self) -> List[Dict]:
        """获取处理日志"""
        return self.process_log
    
    def save_merged_data(self, output_path: str) -> str:
        """保存合并后的数据"""
        if self.merged_df is None:
            raise ValueError("没有可保存的数据")
        
        self.merged_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        self.log("保存数据", f"已保存到 {output_path}", "success")
        
        return output_path

    def _normalize_column_name(self, col: Any) -> str:
        """最小化列名归一化：去空白、去 pandas 重复列后缀 .1/.2..."""
        s = str(col).strip()
        s = re.sub(r"\s+", " ", s)
        s = re.sub(r"\.(\d+)$", "", s)
        return s

    def _select_best_sheet(self, file_path: str):
        """选择默认分析 sheet：优先列数最多"""
        try:
            with pd.ExcelFile(file_path) as xls:
                sheet_names = list(xls.sheet_names or [])
        except Exception:
            return 0

        if len(sheet_names) <= 1:
            return sheet_names[0] if sheet_names else 0

        best = {"sheet": sheet_names[0], "col_count": -1, "row_est": -1}

        for sheet in sheet_names:
            try:
                header_df = pd.read_excel(file_path, sheet_name=sheet, nrows=0)
                col_count = len(header_df.columns)
            except Exception:
                continue

            if col_count > best["col_count"]:
                best = {"sheet": sheet, "col_count": col_count, "row_est": -1}
                continue

            if col_count == best["col_count"]:
                if best["row_est"] < 0:
                    best["row_est"] = self._estimate_sheet_rows(file_path, best["sheet"])
                row_est = self._estimate_sheet_rows(file_path, sheet)
                if row_est > best["row_est"]:
                    best = {"sheet": sheet, "col_count": col_count, "row_est": row_est}

        return best["sheet"]

    def _estimate_sheet_rows(self, file_path: str, sheet_name: str) -> int:
        """粗略估算 sheet 数据行数"""
        try:
            df0 = pd.read_excel(file_path, sheet_name=sheet_name, usecols=[0])
            return int(df0.dropna(how="all").shape[0])
        except Exception:
            return 0
