// 声明JSON文件模块类型
declare module '*.json' {
  const value: any
  export default value
}

// 特别声明测试病历数据文件
declare module '../../../tests/backend/test_data/test_medical_records.json' {
  const value: any[]
  export default value
}
