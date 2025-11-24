# login/views.py
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login
from django.shortcuts import render, redirect
from login.models import UserProfile


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
            # 检查用户类型是否匹配
            try:
                user_profile = UserProfile.objects.get(user=user)
                if user_profile.user_type != user_type:
                    messages.error(request, f'该账号是{user_profile.get_user_type_display()}账号，请使用正确的身份登录')
                    return render(request, "login.html")
            except UserProfile.DoesNotExist:
                messages.error(request, '用户资料不存在，请联系管理员')
                return render(request, "login.html")

            auth_login(request, user)

            # 将用户名存入session，作为商家名
            request.session['merchant_name'] = username

            # 根据用户类型重定向到不同页面
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