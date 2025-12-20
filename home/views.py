from django.http import Http404
from django.shortcuts import render, redirect
from django.views import View

INFO_PAGES = {
    'terms': {
        'title': 'SpeedEats 服务条款',
        'lead': '规范 SpeedEats 平台的使用方式，确保顾客、商家、骑手与平台之间的协作高效、安全、透明。',
        'updated_at': '2025-12-10',
        'sections': [
            {
                'title': '用户基本义务',
                'paragraphs': [
                    '您需要保证注册信息准确、真实，如联系方式、用户类型等信息发生变更请及时更新。',
                    '请合理使用 SpeedEats，禁止以任何形式尝试攻击、爬取或绕过系统限制。'
                ],
                'bullets': [
                    '保持同一账号唯一且安全，禁止共享或出售账号。',
                    '仅在法律允许范围内发布餐品、订单或配送相关信息。'
                ],
            },
            {
                'title': '订单与结算',
                'paragraphs': [
                    '顾客确认下单即视为认可商家提供的商品及价格，若需退款请通过客户支持流程处理。',
                    '商家需确保菜品描述、折扣信息真实有效，并在订单接入后按承诺履约。'
                ],
            },
            {
                'title': '违规处理',
                'paragraphs': [
                    '一旦发现作弊、滥用优惠、恶意评价等行为，平台有权暂停或终止账号。',
                    '严重违规将被上报至所在地监管部门，并保留追究法律责任的权利。'
                ],
            },
        ],
    },
    'privacy': {
        'title': '隐私政策',
        'lead': '我们遵循最小授权原则收集与使用您的信息，并在北京航空航天大学的合规要求下进行保护。',
        'updated_at': '2025-12-10',
        'sections': [
            {
                'title': '收集哪些信息',
                'paragraphs': [
                    '基础信息：用户名、电话、角色类型，用于创建账号与身份校验。',
                    '业务数据：下单记录、评价记录、配送轨迹，以便精准调度与质量追踪。'
                ],
            },
            {
                'title': '信息如何使用',
                'bullets': [
                    '根据您的角色展示相应的业务模块和待办事项。',
                    '在算法中匿名化统计，优化派单、补贴和安全策略。',
                    '在您授权的情况下，向客服或学校项目导师提供必要的排障数据。'
                ],
            },
            {
                'title': '数据安全与存储',
                'paragraphs': [
                    '所有敏感字段（如密码）均经过哈希或脱敏，数据库访问仅限项目成员。',
                    '出现数据泄露风险时，我们会第一时间通知受影响用户并提供应急措施。'
                ],
            },
        ],
    },
    'security': {
        'title': '安全说明',
        'lead': 'SpeedEats 在系统设计阶段即融入安全基因，从代码、数据库、运维多层面保证平台可靠。',
        'updated_at': '2025-12-10',
        'sections': [
            {
                'title': '多层防护',
                'bullets': [
                    '账号层：密码加密存储，支持密码找回和强制重置。',
                    '传输层：敏感接口通过 HTTPS（线上部署时）与签名机制防止被劫持。',
                    '应用层：原生 SQL 操作配合参数化，避免注入风险。'
                ],
            },
            {
                'title': '团队自检机制',
                'paragraphs': [
                    '来自北京航空航天大学的成员会定期 review 关键模块，更新依赖并修复潜在漏洞。',
                    '评分、订单等关键操作均配备风控日志，支持快速回溯。'
                ],
            },
            {
                'title': '应急响应',
                'paragraphs': [
                    '如发现异常登录或订单，我们会冻结相关账号，通知用户并指导修改密码。',
                    '欢迎通过「联系 SpeedEats」页面直接向团队报告安全问题。'
                ],
            },
        ],
    },
    'contact': {
        'title': '联系 SpeedEats 团队',
        'lead': '无论是产品建议、课程合作还是制度咨询，欢迎与我们取得联系。',
        'updated_at': '2025-12-10',
        'sections': [
            {
                'title': '核心渠道',
                'bullets': [
                    '电子邮箱：speedeats@buaa.edu.cn',
                    'GitHub Issues：ConnectC/SpeedEats 仓库',
                    '课程导师：北京航空航天大学 软件工程专业负责人'
                ],
            },
            {
                'title': '响应承诺',
                'paragraphs': [
                    '课程周期内工作日 24 小时内回复，寒暑假视项目安排尽快反馈。',
                    '安全或停机类问题将优先处理并实时同步进展。'
                ],
            },
        ],
        'contact_methods': [
            {'label': 'GitHub', 'value': 'https://github.com/ConnectC/SpeedEats'},
            {'label': '邮箱', 'value': 'speedeats@buaa.edu.cn'},
            {'label': '地址', 'value': '北京市海淀区学院路 37 号 · 北京航空航天大学'},
        ],
    },
}


class HomeView(View):
    def get(self, request):
        return render(request, 'home.html')


def redirect_to_login(request):
    """重定向到登录页面"""
    return redirect('login')


def _render_info_page(request, page_key):
    page = INFO_PAGES.get(page_key)
    if not page:
        raise Http404('Page not found')
    page = {**page, 'slug': page_key}
    return render(request, 'info/page.html', {'page': page})


def terms(request):
    return _render_info_page(request, 'terms')


def privacy(request):
    return _render_info_page(request, 'privacy')


def security(request):
    return _render_info_page(request, 'security')


def contact(request):
    return _render_info_page(request, 'contact')
