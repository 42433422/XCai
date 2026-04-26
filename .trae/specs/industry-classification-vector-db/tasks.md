# Tasks

- [x] Task 1: 扩展 CatalogItem 数据模型，新增保密级和行业分类字段
  - [x] Task 1.1: 在 models.py 中为 CatalogItem 增加 security_level、industry_code、industry_secondary、description_embedding 字段
  - [x] Task 1.2: 在 init_db() 中增加列迁移逻辑，确保现有数据库平滑升级

- [x] Task 2: 实现标准化行业分类体系
  - [x] Task 2.1: 创建 industry_taxonomy.py 定义完整的行业分类树（一级+二级）
  - [x] Task 2.2: 提供行业分类查询 API 端点

- [x] Task 3: 集成向量数据库实现语义检索
  - [x] Task 3.1: 安装 chromadb 依赖
  - [x] Task 3.2: 创建 vector_store.py 实现向量索引的初始化、插入、查询
  - [x] Task 3.3: 实现语义搜索 API 端点 /v1/catalog/search-semantic
  - [x] Task 3.4: 实现相似推荐 API 端点 /v1/catalog/recommend-similar

- [x] Task 4: 更新 Catalog API 支持新字段
  - [x] Task 4.1: 修改 catalog_api.py 的上传端点，接收 security_level 和 industry 字段
  - [x] Task 4.2: 修改列表端点支持 security_level 过滤
  - [x] Task 4.3: 修改 facets 端点返回 security_level 分布

- [x] Task 5: 前端商店页面扩展
  - [x] Task 5.1: AiStoreView 新增保密级筛选 chip 行
  - [x] Task 5.2: 商品卡片显示保密级标签（不同颜色）
  - [x] Task 5.3: 行业筛选改为下拉树形选择器（支持一二级行业）

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 1]
- [Task 4] depends on [Task 1]
- [Task 5] depends on [Task 4]
