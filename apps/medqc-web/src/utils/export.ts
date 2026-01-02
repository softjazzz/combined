import * as XLSX from 'xlsx'

/**
 * 导出数据到 Excel 文件
 * @param data 要导出的数据数组 (JSON对象数组)
 * @param fileName 导出的文件名 (不含后缀)
 * @param sheetName 工作表名称
 * @param headerMap 表头映射 (key: data中的key, value: Excel表头名称)
 */
export function exportToExcel<T extends Record<string, any>>(
  data: T[],
  fileName: string,
  sheetName: string = 'Sheet1',
  headerMap?: Record<string, string>
) {
  // 1. 处理表头映射
  let exportData = data
  if (headerMap) {
    exportData = data.map(item => {
      const newItem: Record<string, any> = {}
      for (const key in headerMap) {
        if (Object.prototype.hasOwnProperty.call(item, key)) {
          newItem[headerMap[key]] = item[key]
        } else {
          // 处理嵌套属性或不存在的属性
          newItem[headerMap[key]] = item[key as keyof T] || ''
        }
      }
      return newItem
    }) as T[]
  }

  // 2. 创建工作簿和工作表
  const workSheet = XLSX.utils.json_to_sheet(exportData)
  const workBook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workBook, workSheet, sheetName)

  // 3. 生成并下载文件
  XLSX.writeFile(workBook, `${fileName}.xlsx`)
}