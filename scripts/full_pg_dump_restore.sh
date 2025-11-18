#!/usr/bin/env bash
#
# Supabase → 阿里云 Supabase 全量迁移脚本（pg_dump/psql 方案）
#
# 使用说明：
#   1. 将下方连接信息替换成实际项目的 host、database、user、password。
#   2. 在可以直连两个 Supabase Postgres 的环境中执行。
#   3. 执行前请先在目标库确认是否需要 TRUNCATE / 备份。
#
# 依赖：
#   - PostgreSQL 13+ 客户端（pg_dump, psql）
#   - 可访问源库、目标库 5432 端口
#   - 充足磁盘空间用于临时压缩文件

set -euo pipefail

#--------- 自定义参数区域 ----------------------------------------------------#

# 源库（海外）连接信息
SOURCE_HOST="db.dgsdkdbjpucyawnyfbdu.supabase.co"
SOURCE_PORT="5432"
SOURCE_DB="postgres"
SOURCE_USER="postgres"
SOURCE_PASSWORD="rK6XqKqU6hB45iMS"

# 目标库（阿里云）连接信息
TARGET_HOST="sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"
TARGET_PORT="5432"
TARGET_DB="postgres"
TARGET_USER="postgres"
TARGET_PASSWORD="Han1979919"

# 临时导出文件（按需调整路径 / 名称）
BACKUP_DIR="$(pwd)/backups"
BACKUP_FILE="${BACKUP_DIR}/supabase_full_$(date +%Y%m%d_%H%M%S).dump"

# 是否在恢复前清空 public schema（谨慎操作，默认 true）
TRUNCATE_PUBLIC="true"

#--------- 无需修改的逻辑区域 --------------------------------------------------#

mkdir -p "${BACKUP_DIR}"

export PGPASSWORD="${SOURCE_PASSWORD}"
echo "📦 导出源库：${SOURCE_HOST}/${SOURCE_DB}"
pg_dump \
  --host "${SOURCE_HOST}" \
  --port "${SOURCE_PORT}" \
  --username "${SOURCE_USER}" \
  --dbname "${SOURCE_DB}" \
  --format=custom \
  --blobs \
  --no-owner \
  --no-privileges \
  --file "${BACKUP_FILE}"

echo "✅ 导出完成 -> ${BACKUP_FILE}"

export PGPASSWORD="${TARGET_PASSWORD}"

if [[ "${TRUNCATE_PUBLIC}" == "true" ]]; then
  echo "⚠️  将在目标库清空 public schema（用户/角色不会被删除）"
  psql \
    --host "${TARGET_HOST}" \
    --port "${TARGET_PORT}" \
    --username "${TARGET_USER}" \
    --dbname "${TARGET_DB}" \
    --command "DO \$\$ DECLARE r RECORD; BEGIN FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE'; END LOOP; END \$\$;"
fi

echo "🚀 恢复数据到目标库：${TARGET_HOST}/${TARGET_DB}"
pg_restore \
  --host "${TARGET_HOST}" \
  --port "${TARGET_PORT}" \
  --username "${TARGET_USER}" \
  --dbname "${TARGET_DB}" \
  --no-owner \
  --no-privileges \
  --jobs=4 \
  "${BACKUP_FILE}"

echo "🎉 全量迁移完成。"
echo "📁 备份文件保存在：${BACKUP_FILE}"
echo "👉 如需释放空间，可手动删除备份目录：${BACKUP_DIR}"
