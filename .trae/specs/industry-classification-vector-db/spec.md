# 行业分类与向量数据库检索系统 Spec

## Why

当前 MOD 商店仅支持基础的 `industry`（行业）和 `artifact`（类型）字段，缺乏：
1. **保密级别分类**：无法区分个人级、企业级、保密级 MOD 的使用场景与权限控制
2. **系统化行业分类**：现有行业字段为自由文本，缺乏标准化分类体系，不利于检索与推荐
3. **智能检索能力**：制作 MOD 时无法根据业务场景智能匹配适合的 AI 员工包

## What Changes

- 新增 **保密级**（security_level）字段：personal（个人级）、enterprise（企业级）、confidential（保密级）
- 新增 **标准化行业分类体系**：覆盖主流行业的层级分类
- 新增 **向量数据库**：用于 MOD/员工包的语义检索与智能推荐
- 扩展 CatalogItem 数据模型与相关 API
- 前端商店页面新增保密级筛选与行业分类树

## Impact

- 受影响模块：catalog_api、catalog_store、models、AiStoreView 前端
- 新增依赖：向量数据库（chromadb 或 sqlite-vss）
- 不影响现有购买、支付、工作流等核心功能

---

## ADDED Requirements

### Requirement: 保密级别分类
系统 shall 为每个 CatalogItem 增加保密级别标识，用于区分适用场景。

#### Scenario: 商品展示保密级标签
- **WHEN** 用户浏览商店商品卡片
- **THEN** 显示保密级标签（个人级/企业级/保密级），使用不同颜色区分

#### Scenario: 按保密级筛选
- **WHEN** 用户点击保密级筛选按钮
- **THEN** 仅展示对应保密级的商品

### Requirement: 标准化行业分类体系
系统 shall 提供标准化的行业分类，覆盖中国国民经济行业分类的主要门类。

#### 行业分类表
| 一级分类 | 二级分类示例 |
|----------|-------------|
| 通用 | 通用工具、效率提升 |
| 制造业 | 汽车制造、电子制造、机械加工 |
| 信息技术 | 软件开发、云计算、大数据 |
| 金融保险 | 银行、证券、保险 |
| 教育培训 | K12、职业教育、高等教育 |
| 医疗健康 | 医院、诊所、健康管理 |
| 零售电商 | 跨境电商、新零售、供应链 |
| 房地产建筑 | 地产开发、建筑设计、物业管理 |
| 物流交通 | 快递物流、航空运输、港口 |
| 能源环保 | 电力、新能源、环保 |
| 农业 | 种植、养殖、农产品加工 |
| 文化传媒 | 影视、游戏、新媒体 |
| 政务公共 | 政府服务、公共服务 |
| 专业服务 | 法律、会计、咨询 |

### Requirement: 向量数据库检索
系统 shall 提供基于向量相似度的智能检索能力，帮助 MOD 制作者找到适合的 AI 员工。

#### Scenario: 语义搜索员工包
- **WHEN** 用户输入自然语言描述业务场景（如"需要处理客户投诉的客服员工"）
- **THEN** 返回最匹配的 AI 员工包推荐列表

#### Scenario: 相似度推荐
- **WHEN** 用户查看某个员工包详情
- **THEN** 展示相似员工包推荐

### Requirement: 数据模型扩展
CatalogItem 模型 shall 增加以下字段：

```python
security_level = Column(String(32), default="personal")  # personal/enterprise/confidential
industry_code = Column(String(16), default="")           # 行业标准编码
industry_secondary = Column(String(64), default="")      # 二级行业
description_embedding = Column(Text, default="")         # 向量嵌入（JSON数组）
```

---

## MODIFIED Requirements

### Requirement: 商品筛选功能
现有筛选功能 shall 扩展支持保密级维度。

**变更内容**：
- AiStoreView 新增保密级 chip 行
- API 支持 security_level 参数过滤

### Requirement: Catalog API
现有 catalog API shall 支持行业编码查询与向量相似度搜索。

**新增端点**：
- `GET /v1/catalog/search-semantic?q=...&limit=...` — 语义搜索
- `GET /v1/catalog/recommend-similar?id=...&limit=...` — 相似推荐

---

## REMOVED Requirements

无删除现有功能。
