# login/views.py
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login
from django.shortcuts import render, redirect

from Project.db_utils import execute_fetchone


USER_TYPE_DISPLAY = {
    'customer': '顾客',
    'rider': '骑手',
    'merchant': '商家',
    'platform': '平台',
}


def _get_user_profile(user_id):
    query = '''
        SELECT user_type
        FROM user_profile
        WHERE user_id = %s
    '''
    return execute_fetchone(query, [user_id])


def login(request):
    # 清除所有消息
    storage = messages.get_messages(request)
    for message in storage:
        pass
    storage.used = True

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type', 'customer')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            user_profile = _get_user_profile(user.id)
            if not user_profile:
                messages.error(request, '用户资料不存在，请联系管理员')
                return render(request, "login.html")

            actual_type = user_profile['user_type']
            if actual_type != user_type:
                display = USER_TYPE_DISPLAY.get(actual_type, actual_type)
                messages.error(request, f'该账号是{display}账号，请使用正确的身份登录')
                return render(request, "login.html")

            auth_login(request, user)
            request.session['merchant_name'] = username

            if user_type == 'rider':
                return redirect('rider')
            elif user_type == 'merchant':
                return redirect('merchant')
            elif user_type == 'platform':
                return redirect('platform')
            else:
                return redirect('customer')
        else:
            messages.error(request, '用户名或密码错误')
    return render(request, "login.html")
