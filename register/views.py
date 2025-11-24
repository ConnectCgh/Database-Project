# register/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate
from django.contrib import messages
from login.models import UserProfile, Customer, Rider, Platform, Merchant
from django.db import connection
import logging
from django.contrib.auth.hashers import make_password

logger = logging.getLogger(__name__)


def check_username_exists(username):
    """
    使用原始SQL查询检查用户名是否存在
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT EXISTS(SELECT 1 FROM auth_user WHERE username = %s)", [username])
        return cursor.fetchone()[0]


def create_user_with_sql(username, password):
    """
    使用SQL创建用户
    """
    with connection.cursor() as cursor:
        # 使用Django的密码哈希函数
        hashed_password = make_password(password)

        # 插入用户记录
        cursor.execute("""
            INSERT INTO auth_user (username, password, is_superuser, is_staff, is_active, date_joined)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, [username, hashed_password, False, False, True])

        # 获取刚创建的用户ID
        cursor.execute("SELECT id FROM auth_user WHERE username = %s", [username])
        user_id = cursor.fetchone()[0]

        return user_id


def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type', 'customer')
        phone = request.POST.get('phone', '')

        logger.info(f"接收到注册请求: username={username}, user_type={user_type}")

        # 验证输入
        if not username or not password:
            messages.error(request, '用户名和密码不能为空')
            return render(request, 'register.html')

        # 使用自定义SQL函数检查用户名是否存在
        if check_username_exists(username):
            messages.error(request, '用户名已存在')
            return render(request, 'register.html')

        try:
            # 使用SQL创建用户
            user_id = create_user_with_sql(username, password)
            logger.info(f"用户创建成功: {user_id}")

            # 获取用户对象用于登录
            user = User.objects.get(id=user_id)

            # 等待信号创建 UserProfile，然后更新它
            import time
            time.sleep(0.1)

            # 获取 UserProfile（信号应该已经创建了）
            try:
                user_profile = user.userprofile
            except UserProfile.DoesNotExist:
                # 如果信号没有工作，手动创建
                user_profile = UserProfile.objects.create(
                    user=user,
                    user_type=user_type,
                    phone=phone
                )
                logger.info("手动创建 UserProfile")
            else:
                # 更新现有的 UserProfile
                user_profile.user_type = user_type
                user_profile.phone = phone
                user_profile.save()
                logger.info("更新现有 UserProfile")

            logger.info(f"用户资料处理成功: {user_profile.id}, 类型: {user_profile.user_type}")

            # 等待信号创建对应的类型记录
            time.sleep(0.1)

            # 检查对应的类型记录是否存在，如果不存在则创建
            if user_type == 'customer':
                if not hasattr(user_profile, 'customer'):
                    Customer.objects.create(
                        user_profile=user_profile,
                        customer_name=username,
                        phone=phone,
                        address="待填写"
                    )
                    logger.info("创建顾客记录")
            elif user_type == 'rider':
                if not hasattr(user_profile, 'rider'):
                    Rider.objects.create(
                        user_profile=user_profile,
                        rider_name=username,
                        phone=phone
                    )
                    logger.info("创建骑手记录")
            elif user_type == 'merchant':
                if not hasattr(user_profile, 'merchant'):
                    Merchant.objects.create(
                        user_profile=user_profile,
                        merchant_name=username,
                        phone=phone,
                        address="待填写"
                    )
                    logger.info("创建商家记录")
            elif user_type == 'platform':
                if not hasattr(user_profile, 'platform'):
                    Platform.objects.create(
                        user_profile=user_profile,
                        platform_name=username,
                        phone=phone
                    )
                    logger.info("创建平台记录")

            # 自动登录 - 需要验证用户
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'注册成功！欢迎{user_type}用户 {username}')
            else:
                messages.error(request, '自动登录失败，请手动登录')
                return redirect('login')

            # 重定向到对应页面
            return redirect('login')

        except Exception as e:
            logger.error(f"注册错误: {str(e)}")
            # 如果创建过程中出现错误，删除已创建的用户
            if 'user_id' in locals():
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM auth_user WHERE id = %s", [user_id])
            messages.error(request, f'注册失败: {str(e)}')
            return render(request, 'register.html')

    return render(request, 'register.html')