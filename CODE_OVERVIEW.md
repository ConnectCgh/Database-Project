# SpeedEats 代码逐文件导读

本指南按照目录→文件→函数/类的颗粒度，解释仓库里每个组件的职责。可以把它当作答辩口述提纲：逐段读就能说清楚“为什么要这么写、每段代码干什么、前后端如何协同”。

---

## 1. 根目录与辅助资料

- `manage.py`：Django CLI 入口，封装 `execute_from_command_line`，所有管理命令（`runserver/migrate` 等）都从这里读取 `Project.settings`。
- `db.sqlite3`：旧的 SQLite 数据文件。本项目现已直连远程 MySQL（写在 `Project/settings.py`），这个文件仅作本地测试或占位。
- `.venv/`：本地虚拟环境，存放依赖和可执行文件，运行时需先 `source .venv/bin/activate`。
- `.git/` 与 `.gitignore`：版本管理目录。`__pycache__/`、迁移缓存等都由 `.gitignore` 排除。
- `.idea/`：JetBrains/IDEA 系列的项目配置（数据源、检查模板等），与业务无关。
- `readme.md`：对 SpeedEats 的整体概述，涵盖技术栈、模块划分、核心数据模型和业务流程，是“官方” README。
- `MODIFICATION_LOG.md`：记录 2025-12-09 的大改动：视图全部改为原生 SQL、引入 `Project/db_utils.py` 等。
- `defense_prep.md`、`team_summary.md`、`大作业答辩.md`：三份中文说明文档，分别对应答辩串词、成员分工总结和 PPT 要点。可直接引用里面的架构/亮点描述。
- `系统实现报告(1).docx`、`系统设计报告(1).docx`：Word 版课程报告，供线下提交。
- 角色应用目录（`home/`、`login/`、`register/`、`customer/`、`merchant/`、`rider/`、`platforme/`、`meal/`、`discount/`、`order/`）下面的 `__init__.py`、`admin.py`、`apps.py`、`tests.py`、`migrations/` 等均遵循 Django 规范：`__init__` 让目录变成包，`apps.py` 注册 AppConfig，`admin/tests` 目前为空壳，`migrations` 记录数据库变更历史。

---

## 2. Django 项目骨架（`Project/`）

- `__init__.py`：把目录声明为 Python 包，供 `DJANGO_SETTINGS_MODULE` 导入。

### 2.1 `settings.py`
- **INSTALLED_APPS**：注册 Django 自带模块 + 9 个业务 app。
- **DATABASES**：把默认数据库指向远程 MySQL（`124.70.86.207`），所以本地调试要么连公网，要么临时改配置。
- **MIDDLEWARE/TEMPLATES/STATIC**：保持 Django 默认设置（暂未启用自定义中间件）。
- **DEFAULT_AUTO_FIELD**：使用 `BigAutoField`，和数据库里 `bigint` 主键对应。

### 2.2 `urls.py`
- 统一路由表：根路径 `""` 映射到 `home.views.HomeView`，再往下是信息页、登录/注册、四大角色接口（顾客/商家/骑手/平台）。所有 AJAX API 均在这里注册，例如 `customer/place-order/`、`merchant/get-discounts/` 等。

### 2.3 `db_utils.py`
原生 SQL 的工具集，全部函数在 `Project` 层使用，以保证跨 app 共用逻辑：

| 函数 | 作用 |
| ---- | ---- |
| `dictfetchall(cursor)` / `dictfetchone(cursor)` | 把 `cursor.fetchall()` 结果转换成字典（列名→值），方便模板直接访问。 |
| `execute_fetchall(query, params=None)` / `execute_fetchone(...)` | 执行查询 SQL 并返回取整后的 `dict` 列表/单条。 |
| `execute_write(query, params=None)` | 执行 INSERT 并返回 `lastrowid`，下单/申请等场景都会用到。 |
| `execute_non_query(query, params=None)` | 执行 UPDATE/DELETE，返回受影响行数。 |
| `quote_table(name)` | 用数据库方言包裹表名，避免与关键字冲突。 |
| `get_entity_by_user(table_name, user_id)` | 通用函数，通过 `user_profile_id` 关联 `customer/merchant/platform/rider` 表；下方再封装 `get_customer_by_user` 等四个快捷函数。 |

### 2.4 `middleware.py`
`MultiSessionTokenMiddleware`（目前未在 `settings.py` 启用）实现“一个账号多个 session token”的能力：
- `_extract_token`：从自定义头 `X-Session-Token`、查询参数、Cookie 中读取令牌。
- `_get_active_session`：查询 `user_session` 表，判定 token 是否有效/未过期。
- `_load_user`：用原生 SQL 读 `auth_user` 并实例化 Django User；设置 `request.user` 实现免密码登录。
- 如果 token 无效，会通过响应删除 cookie，防止死循环。

### 2.5 `asgi.py` / `wsgi.py`
标准 Django 启动脚本，分别用于异步和 WSGI 网关。

---

## 3. 身份与公共模型

### 3.1 `login/`（账号、角色、入驻/签约）

- `apps.py`：`LoginConfig.ready()` 自动导入 `login.models`，保证信号（`post_save`）在启动时注册。
- `models.py`：
  - **数据模型**：`UserProfile` 扩展 `auth_user`，保存 `user_type/phone/时间戳`；`Customer/Merchant/Platform/Rider` 四张角色表各有名称、电话及评价字段；`EnterRequest`（商家→平台入驻）、`SignRequest`（骑手→平台签约）、`MerchantPlatformDiscount`（商家平台折扣）。所有表都设置了 `db_table`，与 MySQL 中的大小写一致。
  - **评分字段**：商家、平台、骑手都有 `rating_score/rating_count`，订单评分会实时更新。
  - **Helper 函数**：`_ensure_*_record` 系列会检测某个 `user_profile_id` 是否已有角色记录，若没有就插入 placeholder（地址为“待填写”等）。`_ensure_user_profile_record` 在创建/保存 `auth_user` 时兜底创建 `user_profile`。
  - **信号**：`create_user_profile/save_user_profile` 监听 `User` 的 `post_save`，`create_user_type_profile/save_user_type_profile` 监听 `UserProfile`，在注册或修改用户类型时自动补齐四张角色表，实现“统一账号，四端共用”。
- `views.py`：
  - `_get_user_profile(user_id)`：用 SQL 查询 `user_profile`，供登录后校验角色类型。
  - `login(request)`：先清空 Django messages，再调用 `authenticate`；额外检查前端选的 `user_type` 与数据库一致，然后 `redirect` 到四端入口并把 `merchant_name` 写到 session。
  - `forgot_password(request)`：校验用户名 + 手机号是否匹配 `user_profile`，再用 `make_password` 更新 `auth_user.password`。成功后写入 session flag，登录页会提示“密码已重置”。
- `templates/`：
  - `login.html`：深色卡片式登录页，顶部四个身份卡片伴随 JS 切换占位符；表单提交时有前端必填校验，消息提示通过自定义弹窗展示。底部链接跳到条款/隐私/安全/联系页面。
  - `forgot_password.html`：输入用户名+电话+新密码并双重确认，支持错误提示与消息自动淡出。
  - `session_manager.html`：展示 token 列表、创建/注销按钮；配合 `user_session` 表和中间件，可以在后台手动发行/吊销 session（还未在路由中启用，但模板已经准备好）。
- `migrations/`：
  - `0001_initial`：建立 `UserProfile` 与四张角色表、`EnterRequest`/`SignRequest`。
  - `0002_alter_enterrequest_status_signrequest`：为申请表增加 `rejected` 状态。
  - `0003_merchantplatformdiscount`：加 `merchant_platform_discount` 多对多表。
  - `0004_*rating*`：给商家/平台/骑手加评分字段。
  - `0005_usersession`：新增 `UserSession` 模型，即多会话 token 存储。
- `admin.py/tests.py`：当前为空，可在此注册模型或写测试。

### 3.2 `register/`

- `views.py` 使用全 SQL 实现注册流程：
  - `check_username_exists(username)`：直接对 `auth_user` 做 `LOWER(username)` 查询，供接口与前端实时校验。
  - `create_user_with_sql(username, password)`：手工执行 `INSERT INTO auth_user`，并返回新用户 ID。
  - `ensure_user_profile(user_id, user_type, phone)`：存在则更新 `user_type/phone`，否则插入 `user_profile`。
  - `ensure_detail_record(...)`：按照角色写入 `customer/rider/merchant/platform` 表。
  - `cleanup_user_records(user_id)`：注册异常时回滚 `user_profile` 和 `auth_user`。
  - `register(request)`：综合上述函数，完成注册 + 自动登录 + 消息提示。
  - `check_username(request)`：GET API，配合前端节流查询。
- `templates/register.html`：与登录页同一视觉体系。顶部身份卡切换，表单包含用户名、电话、密码/确认密码、同意条款。底部 JS 负责：
  - 用户名实时校验（500ms debounce，调用 `/register/check-username/`）。
  - 密码强度条、必填项提示、提交加载状态。
  - 自动淡出 Django message。
- `apps/admin/tests`：占位。

### 3.3 `home/`

- `views.py`：
  - `HomeView`：渲染 `home.html`，作为根页面。
  - `INFO_PAGES`：条款/隐私/安全/联系的静态文案。
  - `_render_info_page(request, page_key)`：读取上面的数据结构并渲染 `info/page.html`。
  - `terms/privacy/security/contact`：四个薄薄的视图函数，调用 `_render_info_page`。
- `templates/home.html`：单页宣传站，包含导航、英雄区、实时数据、角色优势、流程时间轴、用户评价等，全部用原生 CSS+Grid 渲染，底部 CTA 按钮链接登录/了解更多。
- `templates/info/page.html`：信息页通用模板，具备返回主页链接、section 循环、提醒条、联系方式栅格等。
- `models.py/tests.py`：暂未使用。

---

## 4. 业务端应用

### 4.1 `customer/`

- `models.py/tests.py`：空壳，所有逻辑直接用 SQL。
- `views.py`：顾客视图函数众多，下表按顺序概述：

| 函数 | 说明 |
| ---- | ---- |
| `_format_decimal(value)` | 用 `Decimal.quantize` 把评分/金额保留两位。 |
| `_normalize_rating(value)` | 校验评分 0~5、允许 0.5 步长，给 `_update_entity_rating` 使用。 |
| `_update_entity_rating(table_name, entity_id, rating_value)` | 直接在商家/平台/骑手/餐品表里累计平均分（`(score*count+new)/(count+1)`）。 |
| `_get_platforms()`/`_get_all_merchants()` | 拉取全部平台/商家的信息及评分。 |
| `_get_platforms_for_merchant(merchant_id)` | 查询某商家已获批的平台列表。 |
| `_get_meals_for_merchant_platform(merchant_id, platform_id)` | 拉取指定商家+平台的餐品，附带类型显示。 |
| `_get_customer(order_user)` | 通过 `get_customer_by_user` 获取当前顾客，若不存在则抛异常。 |
| `_get_customer_order_rows(customer_id)` | 关键函数：一次查询订单、平台、商家、折扣、骑手，再补齐 `order_item` 与 `order_meal_rating` 表数据，最终构建 `order_map`。 |
| `_format_meal_summary(meals)`、`_build_order_context(rows)`、`_build_order_payload(rows)` | 在 `customer()` 视图和 API 返回值中复用，分别构建模板上下文与 JSON payload。 |
| `_get_enter_request` / `_get_available_discounts` / `_get_discount_for_order` / `_fetch_meal` / `_get_available_meal_ids` | 下单前的合法性校验，用于确认商家确实在该平台上架、折扣可用、餐品属于该商家。 |
| `_build_in_clause(values)` | 生成 `IN (%s,%s,...)` 占位符。 |
| `_meal_type_filters(meal_type)` | 搜索时处理“午餐/晚餐/午晚”之间的包含关系。 |
| `customer(request)` | 顾客首页：拉取当前顾客、所有平台、各商家+平台的餐品、折扣清单、订单列表，再渲染 `customer.html`。 |
| `get_merchant_detail(request, merchant_id, platform_id)` | Ajax，用于弹窗展示指定平台下的餐品+折扣。 |
| `place_order(request)` | 接收 JSON 载荷（商家、平台、餐品数组、折扣、总价），逐条校验餐品后写入 `order` 和 `order_item` 表，初始状态 `unassigned`。 |
| `get_orders(request)` | Ajax 刷新订单表格，返回 `_build_order_payload` 的结果。 |
| `search_merchants(request)` | 支持平台/商家/餐品名/餐品类型过滤，返回满足条件的商家+平台+餐品列表供前端展示。 |
| `delete_order(request, order_id)` | 顾客仅能删除 `unassigned` 或 `cancelled` 状态订单。 |
| `pickup_order(request, order_id)` | 验证订单属于自己且状态 `ready`，更新为 `completed` 并返回取餐成功提示。 |
| `rate_order(request, order_id)` | 顾客评价接口：校验订单完成且未评分 → 插入 `order_rating`、`order_meal_rating` → 调用 `_update_entity_rating` 更新商家/平台/骑手/餐品的平均分 → 返回评分详情。 |

- `templates/customer.html`：一个大型仪表盘，主要分为：
  - 左侧导航（平台列表、商家广场、我的订单、评价中心等）。
  - 平台筛选、商家卡片、搜索表单、订单表格、评分面板。
  - 两个模态框：`merchant-detail-modal`（展示餐单并下单）、`rate-order-modal`（完成后评分）。
  - 底部 JS 负责：
    - 菜单切换、模态框显隐、CSRF token 获取。
    - 渲染商家/餐品卡片、加载/刷新订单、展示状态徽章。
    - 发起 `/customer/get-merchant-detail/`、`place-order`、`get-orders`、`search-merchants`、`delete-order`、`pickup-order`、`rate-order` 等 fetch 请求。
    - 订单操作按钮绑定（删除、取餐、去评价），以及评分表单的动态行（为每个餐品生成输入框）。

### 4.2 `merchant/`

- `views.py` 中的辅助函数与对外 API：

| 函数 | 说明 |
| ---- | ---- |
| `_get_merchant(user)` | 基于登录用户查出对应商家，若无则抛 `ValueError`。 |
| `_get_platform(platform_id)` / `_get_platforms_by_status` | 平台信息及审批状态列表。 |
| `_merchant_joined_platform(merchant_id, platform_id)` | 判断商家是否已被该平台批准。 |
| `_get_meal` / `_get_meals_for_merchant` | 餐品查询，含 platform join。 |
| `_format_meals_for_context` | 把 SQL 结果包装成模板需要的结构。 |
| `_get_discounts_for_merchant` / `_get_available_discounts` | 读取指定商家在每个平台设定的折扣，以及全局折扣字典。 |
| `_get_orders_for_merchant` | 与顾客端类似，聚合订单 + 订单项。 |
| `_format_meal_summary` / `_format_orders_for_context` / `_format_orders_for_payload` | 格式化订单，分别用于模板和 JSON 返回。 |
| `_get_discount(discount_id)` | 校验折扣存在。 |
| `apply_platform` | POST API，提交入驻申请或把被拒绝的申请重置为 `pending`。 |
| `add_meal` / `edit_meal` / `delete_meal` | 餐品 CRUD，都会先校验是否已入驻目标平台、价格是否合法。 |
| `get_meals` | Ajax 获取餐品列表。 |
| `set_discount` / `edit_discount` / `delete_discount` / `get_discounts` | 商家在平台上设置/更新/删除折扣，底层操作 `merchant_platform_discount` 表。 |
| `get_orders` | Ajax 获取订单列表。 |
| `delete_order` | 仅允许删除未分配骑手的订单。 |
| `merchant(request)` | 主页视图，汇总商家名称、餐品、已入驻/待审核/未申请平台、折扣、订单等上下文，渲染 `merchant.html`。 |

- `templates/merchant.html`：
  - 带侧边栏的后台 UI，包含餐品管理、平台入驻、折扣设置、订单监控四大内容卡片。
  - 模态框：新建/编辑餐品、编辑折扣。
  - JS 功能：菜单切换、表单提交、折扣动态刷新（`updateDiscountsTable`）、处理 `/merchant/*` fetch 请求、平台入驻按钮的加载状态、订单筛选提示。

### 4.3 `rider/`

- `views.py` 函数：

| 函数 | 说明 |
| ---- | ---- |
| `_get_rider(user)` | 通过 `get_rider_by_user` 获取骑手资料，若无则抛出。 |
| `_get_platform(platform_id)`、`_get_platforms_by_status` | 查询平台信息/签约状态。 |
| `_has_sign_request(rider_id)` | 判断是否已有任何签约记录，防止重复申请。 |
| `_get_signed_platform_ids` | 返回已批准平台 ID 列表。 |
| `_build_in_clause`、`_format_meal_summary`、`_attach_meal_summaries` | 复用逻辑，把订单和订单项拼好。 |
| `_get_unassigned_order_groups(platform_ids)` | 获取骑手能看到的待接订单（限定在自己签约的平台，且 `status='unassigned'`）。 |
| `_get_accepted_order_groups(rider_id)` | 获取骑手自己接的订单（状态 `assigned/ready`）。 |
| `apply_platform` | 提交签约申请，只允许一次。 |
| `accept_orders` / `cancel_orders` / `complete_orders` | 分别把订单状态改为 `assigned`（并绑定骑手）、撤销到 `unassigned`、或标记为 `ready`（顾客待取）。 |
| `rider(request)` | 渲染 `rider.html`，上下文包含骑手名称、已/待签约平台、可接订单、已接订单等。 |

- `templates/rider.html`：
  - 结构与商家/平台类似，侧边栏 + 多内容卡片：平台签约、待接订单列表（按商家+顾客显示）、已接订单表格。
  - JS：导航切换、获取 CSRF、`handleOrderAction()` 统一封装接单/取消/完成的 fetch 调用，按钮显示加载状态并在成功后刷新页面。

### 4.4 `platforme/`（平台端）

- `views.py` 函数：

| 函数 | 说明 |
| ---- | ---- |
| `_get_platform(user)` | 通过 `get_platform_by_user` 获取当前平台实体。 |
| `_get_merchant_requests(platform_id, status)` / `_get_rider_requests(...)` | 查询各状态的商家入驻/骑手签约申请，打包成 `{id, merchant/rider{...}}`。 |
| `_get_orders(platform_id)` | 拉取该平台下所有订单及订单项，供统计与表格显示。 |
| `_format_meal_summary` / `_format_orders_for_context` / `_get_order_counts` | 构造模板数据和顶部统计数字（总订单/未分配/已分配/待取）。 |
| `_get_enter_request_entry` / `_get_sign_request_entry` | 在审批/移除时确认记录仍处于对应状态。 |
| `platform(request)` | 后台主页，把待审核/已通过的商家/骑手、订单列表、统计数字注入模板。 |
| `approve_merchant_request` / `reject_merchant_request` / `remove_merchant` | 审批/拒绝/移除商家入驻（本质是更新或删除 `enter_request`）。 |
| `approve_rider_request` / `reject_rider_request` / `remove_rider` | 同上，用于骑手 `sign_request`，通过时顺便把 `rider.status` 设为 `online`，移除时设回 `offline`。 |
| `delete_order` | 平台清理未分配的异常订单。 |

- `templates/platform.html`：
  - 与商家后台类似，但内容卡片包括审批看板、订单统计、实时订单表。
  - JS：导航切换、统一的点击代理（`document.addEventListener('click', ...)`）处理商家/骑手审批以及删除订单的 fetch 请求，每个按钮都会显示“处理中...”并在完成后刷新。

### 4.5 `order/`

- `models.py`：
  - `Order`：关联顾客/平台/商家/折扣/骑手，包含价格和状态（`unassigned/assigned/ready/completed/cancelled`）。
  - `OrderItem`：一张订单拆成多条餐品，记录数量、单价、小计。
  - `OrderRating`：一单一次评分，分别记录商家/平台/骑手的平均分。
  - `OrderMealRating`：对每个 `OrderItem` 的评分，便于计算餐品评分。
- `migrations/`：
  - `0001_initial`：最初版本，订单直接挂载一个餐品字段。
  - `0002`：精简状态机 & 加入 `OrderRating`。
  - `0003`：正式引入 `OrderItem`、`OrderMealRating`，并包含两段数据迁移脚本，把旧数据拆成订单项和餐品评分。
- `views.py/tests.py/admin.py`：目前未实现（所有业务由其他 app 负责）。

### 4.6 `meal/`

- `models.py`：`Meal` 关联商家与平台，字段包含名称、价格、类型（早餐/午餐/晚餐/午晚）、创建/更新时间，以及评分字段。
- `migrations/0001-0003`：依次创建表、补充 `platform` 外键、增加评分统计。
- 其余文件为空壳。

### 4.7 `discount/`

- `models.py`：`Discount` 只有一个 `Decimal` 类型的 `discount_rate`（0~1 区间，表示折扣比例）。
- `migrations/0001` 创建表，`0002_discount_platform` 给折扣增加一个可选的 `platform` 外键（便于按平台预置折扣），不过在业务层仍通过 `merchant_platform_discount` 建立商家-平台-折扣的绑定。

---

## 5. 模板与前端逻辑总览

虽然大部分页面都在各 app 的 `templates/` 内部，但可以按角色记住共同规律：

- **通用元素**：所有页面都内置 `{% csrf_token %}`，并在 JS 中通过 `querySelector('[name=csrfmiddlewaretoken]')` 取值，再设置到 `fetch` 的 `X-CSRFToken` 头；退出登录统一是 `window.location.href = '/login/'`。
- **样式**：深色背景 + 亮黄色（`#ffc107`）强调色，组件（卡片/按钮/状态标签）在四个角色页中保持一致，方便老师视觉辨认。
- **脚本模式**：以 `document.querySelectorAll` + `forEach` 绑定事件，或使用事件代理（`document.addEventListener('click', handler)`)；所有异步操作都包裹 `fetch().then(response => response.json())` 并显示 `alert`。

各模板的亮点：

| 模板 | 作用与关键 JS |
| ---- | ---- |
| `home/templates/home.html` | 品牌官网风格 landing page，含导航、英雄区、优势卡片、数据卡、流程时间线、用户评价、FAQ、CTA。 |
| `home/templates/info/page.html` | 条款/隐私/安全/联系的通用布局，支持段落、列表、提示条和联系卡片。 |
| `login/templates/login.html` | 支持四种身份选择、错题提示弹窗、表单校验、消息自动淡出。 |
| `login/templates/forgot_password.html` | 回到主页/登录链接、三输入框校验、消息提示、底部信息链接。 |
| `register/templates/register.html` | 身份卡切换、实时用户名查重、密码强度条、条款勾选、错误提示/成功提示。 |
| `customer/templates/customer.html` | 平台栏、商家列表、搜索面板、订单表格、评价面板、下单/评分模态。JS 重头戏：`displayMerchantDetail`、`renderMerchants`、`loadOrders`、`updateOrdersTable`、`openRatingModal`、`deleteOrder/pickupOrder/submitRating` 等函数。 |
| `merchant/templates/merchant.html` | 餐品列表（含新增/编辑/删除按钮）、平台申请卡、折扣表+模态、订单表。JS 包括 `openModal`、`populatePlatformOptions`、`updateDiscountsTable`、`deleteDiscount` 等操作。 |
| `rider/templates/rider.html` | 平台签约卡片（按钮调用 `/rider/apply-platform/`）、待接/已接订单卡，JS 用 `handleOrderAction` 统一封装接单/取消/完成。 |
| `platforme/templates/platform.html` | 商家/骑手审批列表、订单统计和订单表，JS 通过点击代理分别调用审批/拒绝/移除/删除 API。 |
| `login/templates/session_manager.html` | Token 列表 + 发 token/吊销按钮，表格显示是否当前 session、过期时间等。 |

---

## 6. 其他仓库目录

- `customer/migrations/`、`merchant/migrations/`、`rider/migrations/`、`platforme/migrations/`、`home/migrations/`：目前只有 `__init__.py`，表示尚未生成迁移（这些 app 没有模型或仍使用共享模型）。
- 所有 `__pycache__/`：Python 编译缓存，无需关注。

---

## 7. 答辩提示：如何串起代码 → 业务流程

1. **注册 → 登录**：讲 `register/views.py` 的 SQL 插入 → `login/models` 信号自动建档 → `login/views.login` 根据 `user_type` 跳转。
2. **商家入驻**：用 `merchant/views.apply_platform` 发起申请 → `platforme/views.approve_merchant_request` 审核通过 → 商家可在 `add_meal/set_discount` 中上架餐品+折扣。
3. **顾客下单**：`customer/views.customer` 拉取商家/餐品 → `customer/templates` 打开下单模态 → `place_order` 写 `order/order_item`。
4. **骑手接单**：`rider/views` 读取签约状态 → `accept_orders/cancel_orders/complete_orders` 切换状态。
5. **顾客取餐+评分**：`pickup_order` 把状态改为 `completed` → `rate_order` 写 `order_rating/order_meal_rating` 并更新商家/平台/骑手/餐品评分。
6. **平台监管**：`platforme/views` 展示审批/统计界面，随时删除未分配订单、移除违规商家/骑手。

只要按这个流程讲，配合本文件的逐函数说明，就能覆盖全部代码点。
