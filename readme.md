SpeedEats 项目解读
====================

项目整体
--------

- **技术栈**：基于 Django 5.2 的多角色外卖系统，九个 app 已在 `Project/settings.py` 注册。路由集中在 `Project/urls.py`，典型的“请求 → 视图函数 → 模板/JSON”流程。
- **部署**：配置的数据库是远程 MySQL（`HOST=124.70.86.207`），`db.sqlite3` 只是遗留文件。`manage.py` 是运行和迁移入口，`python manage.py runserver` 会读取 `Project/settings.py`。
- **前端形态**：没有独立构建工具，全部是各 app `templates/` 下的纯 HTML + inline CSS/JS。页面通过 `fetch` 与后端视图的 `JsonResponse` 交互，CSRF 令牌手动注入。
- **用户体系**：`login/models.py` 中的 `UserProfile` 一对一扩展 `auth.User`，并通过 `post_save` 信号自动同步到四个角色表（顾客/骑手/商家/平台），保证跨 app 使用统一身份。

目录与前后端划分
----------------

| 模块 | 后端代码 | 前端模板 / JS | 说明 |
| ---- | -------- | ------------- | ---- |
| 项目配置 | `Project/settings.py`, `Project/urls.py`, `manage.py` | – | 负责全局配置、路由、命令入口。 |
| 登录/注册 | `login/views.py`, `register/views.py` | `login/templates/login.html`, `register/templates/register.html` | 登录校验用户类型、注册直接写 `auth_user` 并填充 `UserProfile`。 |
| 顾客端 | `customer/views.py` | `customer/templates/customer.html` | 展示商家/平台/折扣，下单、搜索、查看/删除订单。 |
| 商家端 | `merchant/views.py` | `merchant/templates/merchant.html` | 平台入驻、餐品 CRUD、折扣配置、订单管理。 |
| 骑手端 | `rider/views.py` | `rider/templates/rider.html` | 平台签约、接单/取消/完成，“商家+顾客”分组展示订单。 |
| 平台端 | `platforme/views.py` | `platforme/templates/platform.html` | 审核商家入驻、骑手签约，监控订单和统计。 |
| 共享模型 | `meal/models.py`, `discount/models.py`, `order/models.py` | – | 餐品、折扣、订单模型供其他 app 复用。 |

核心数据模型
------------

- `login/models.py`
  - `UserProfile`：扩展 Django 自带用户，记录 `user_type`、手机号等；信号 `create_user_type_profile`/`save_user_type_profile` 自动创建或补齐四个角色表。
  - `Customer`/`Merchant`/`Platform`/`Rider`：与 `UserProfile` 一对一，分别补充地址、状态等业务字段。
  - `EnterRequest`：商家入驻申请，限制每个 (商家, 平台) 组合唯一。
  - `SignRequest`：骑手签约申请，同样限制唯一组合。
  - `MerchantPlatformDiscount`：商家在特定平台挂载折扣，顾客下单时据此过滤。
- 其他 app
  - `meal/models.py`：餐品属于某商家+平台组合，包含价格与供应时段。
  - `discount/models.py`：折扣率 `Decimal` 字段（0–1）。
  - `order/models.py`：订单关联顾客、平台、商家、餐品、骑手、折扣，并用 `status` 跟踪 `unassigned/assigned/ready/completed/cancelled`。

业务模块详解
------------

### 登录与注册

- `login/views.py:8`：登录时清空消息、认证用户、校验 `UserProfile.user_type`，成功后写入 session 并跳转对应角色页。
- `register/views.py:44`：注册使用原始 SQL 写入 `auth_user`，等待信号创建 `UserProfile`，若失败则手动补齐，并按用户类型创建角色实体；最后自动登录并提示成功。
- 前端模板参考 `login/templates/login.html`, `register/templates/register.html`，提供四种身份卡片切换并在脚本中处理提交。

### 顾客端

- `customer/views.py`
  - `customer()`：汇总顾客信息、所有平台和入驻商家，打包商家在各平台下的餐品及折扣。
  - `get_merchant_detail()`：校验商家是否在平台入驻，返回餐品和折扣详情。
  - `place_order()`：按所选餐品逐条创建 `Order`（初始 `unassigned`），可附加折扣；`JsonResponse` 提示成功或错误。
  - 其他视图提供订单列表、商家搜索、订单删除/取餐。
- 模板 `customer/templates/customer.html`：
  - 暗黑仪表盘 UI，含平台筛选、商家卡片、订单表格和模态下单界面。
  - 底部脚本（从 `customer/templates/customer.html:953` 起）处理导航切换、拉取商家详情、计算折扣价格、`fetch` 提交订单/搜索/删除/取餐等。

### 商家端

- `merchant/views.py`
  - `apply_platform()`：提交入驻申请，避免重复或自动重置被拒绝的申请。
  - `add_meal`/`edit_meal`/`delete_meal`/`get_meals`：CRUD 餐品，所有操作都先确认商家已在目标平台 `approved`。
  - `set_discount`/`edit_discount`/`delete_discount`/`get_discounts`：管理 `MerchantPlatformDiscount`。
  - `get_orders`/`delete_order`：查看或删除未分配骑手的订单。
  - `merchant()`：组装模板所需数据（所有平台、已入驻/待审核/未申请、折扣、订单等）。
- 模板 `merchant/templates/merchant.html`：
  - 侧边栏 + 多内容卡片，含餐品列表、平台申请、折扣、订单。
  - 多个模态框（添加/编辑餐品、编辑折扣），JS（`merchant/templates/merchant.html:977` 起）负责导航切换、订单筛选、`fetch` 调用后端、动态刷新列表。

### 骑手端

- `rider/views.py`
  - `apply_platform()` 限制一个骑手只能发起一次签约申请。
  - `accept_orders`/`cancel_orders`/`complete_orders`：基于骑手已签约的平台，对特定商家+顾客组合的订单批量更新骑手和状态。
  - `rider()` 渲染页面时按“商家+顾客”聚合待接单与已接单数据，并列出已签约、待审批、未申请的平台。
- 模板 `rider/templates/rider.html` 与脚本（`rider/templates/rider.html:606`）包含平台申请按钮、订单卡片、按钮事件和 `fetch` 逻辑。

### 平台端

- `platforme/views.py`
  - `platform()`：取当前平台对象，收集待审核/已入驻商家、待审核/已签约骑手、全部订单及统计。
  - 审批/拒绝/移除商家或骑手（`approve_merchant_request`, `reject_merchant_request`, `remove_merchant`, `approve_rider_request`, `reject_rider_request`, `remove_rider`）。
  - `delete_order()`：删除仍未分配骑手的订单。
- 模板 `platforme/templates/platform.html` 和脚本（自 `platforme/templates/platform.html:678` 起）实现后台视图、订单筛选、审批按钮事件、`fetch` 调用等。

端到端流程示例
--------------

1. **注册与身份**：新用户通过注册页提交账号/密码/手机号/身份；后台写入 `auth_user`，信号或兜底逻辑创建 `UserProfile` 与对应角色实体，并自动登录。
2. **商家入驻**：商家在控制台发起平台申请，生成 `EnterRequest`。平台管理员在平台端批准后，商家方可在该平台添加餐品或设置折扣。
3. **菜品与折扣**：商家在“餐品管理”中 CRUD 菜品，在“折扣管理”中关联 `Discount`，顾客查看商家详情时只会看到对应平台下的餐品/折扣。
4. **顾客下单**：顾客在商家卡片中打开模态框，选择餐品和折扣后调用 `/customer/place-order/`，为每个餐品生成一条 `Order`（`unassigned`）。
5. **骑手接单**：骑手在签约的平台范围内看到待接订单，点击“接单”将 `Order` 批量写入自己名下并设为 `assigned`，完成取餐后更新为 `ready`。
6. **顾客取餐**：顾客在订单表格中对 `ready` 状态订单点击“取餐”，后端删除订单并返回成功提示。
7. **平台监管**：平台端可以审批入驻/签约、统计订单、删除未分配订单，确保整个流程受控。

Django 相关提示（面向不熟悉 Django 的同学）
------------------------------------

- **视图函数**：都位于 `views.py`，实质是接收 `request` 并返回 `render()`（HTML）或 `JsonResponse()`（JSON）的普通函数，上面经常加 `@login_required` 限制登录。
- **URL 配置**：`Project/urls.py` 中的 `path()` 把 URL 映射到视图，例如 `path("customer/place-order/", customer_views.place_order, ...)`；开发新功能时需要把视图挂在这里。
- **模板渲染**：`render(request, "customer.html", context)` 类似 Jinja2，会找 `customer/templates/customer.html` 并传入 `context` 里的变量。
- **CSRF**：默认开启，JS `fetch` 提交 POST/DELETE 需要自行附带 `X-CSRFToken`，模板中通常通过 `<input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">` 或脚本中的 `getCSRFToken()` 获取。
- **数据库迁移**：修改 `models.py` 后运行 `python manage.py makemigrations` 和 `python manage.py migrate`；当前项目指向远程 MySQL，如需本地调试可临时改成本机数据库。

后续建议
--------

1. 本地调试时建议把 `DATABASES["default"]` 切到本机 MySQL 或 SQLite，避免误操作线上数据。
2. 目前各 `tests.py` 为空，可为关键业务流（注册、下单、接单、审批）编写 `pytest`/`Django TestCase`，在改动模型或视图时提供回归保障。
