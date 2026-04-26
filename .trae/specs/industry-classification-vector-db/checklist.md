# Checklist

- [x] CatalogItem 模型包含 security_level 字段，默认值为 "personal"
- [x] CatalogItem 模型包含 industry_code 字段（行业标准编码）
- [x] CatalogItem 模型包含 industry_secondary 字段（二级行业）
- [x] CatalogItem 模型包含 description_embedding 字段（向量嵌入）
- [x] init_db() 包含新字段的列迁移逻辑，现有数据库可平滑升级
- [x] industry_taxonomy.py 包含完整的行业分类树（一级14类，二级完整）
- [x] 行业分类查询 API 可用（GET /v1/catalog/industries）
- [x] chromadb 依赖已安装且向量数据库可正常初始化
- [x] 语义搜索 API 可用（GET /v1/catalog/search-semantic）
- [x] 相似推荐 API 可用（GET /v1/catalog/recommend-similar）
- [x] 商品上传 API 支持接收 security_level 和 industry_code 字段
- [x] 商品列表 API 支持 security_level 参数过滤
- [x] facets API 返回 security_level 分布数据
- [x] 前端商店页面有保密级筛选 chip 行（全部/个人级/企业级/保密级）
- [x] 商品卡片显示保密级标签，三种级别颜色不同
- [x] 行业筛选支持一二级分类选择
