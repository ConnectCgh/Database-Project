# register/views.py
import logging

from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.hashers import make_password
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET

from Project.db_utils import execute_fetchone, execute_non_query, execute_write

logger = logging.getLogger(__name__)


def check_username_exists(username):
    """
    使用原始SQL查询检查用户名是否存在
    """
    if not username:
        return False
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM auth_user WHERE LOWER(username) = LOWER(%s) LIMIT 1", [username])
        return cursor.fetchone() is not None


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


def ensure_user_profile(user_id, user_type, phone):
    profile = execute_fetchone('SELECT id FROM user_profile WHERE user_id = %s', [user_id])
    if profile:
        execute_non_query(
            '''
            UPDATE user_profile
            SET user_type = %s,
                phone = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            ''',
            [user_type, phone, profile['id']],
        )
        return profile['id']

    return execute_write(
        '''
        INSERT INTO user_profile (user_id, user_type, phone, created_at, updated_at)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''',
        [user_id, user_type, phone],
    )


def ensure_detail_record(profile_id, user_type, username, phone):
    if user_type == 'customer':
        existing = execute_fetchone('SELECT id FROM customer WHERE user_profile_id = %s', [profile_id])
        if not existing:
            execute_write(
                '''
                INSERT INTO customer (user_profile_id, customer_name, phone, address, created_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ''',
                [profile_id, username, phone, '待填写'],
            )
    elif user_type == 'rider':
        existing = execute_fetchone('SELECT id FROM rider WHERE user_profile_id = %s', [profile_id])
        if not existing:
            execute_write(
                '''
                INSERT INTO rider (user_profile_id, rider_name, phone, status, created_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ''',
                [profile_id, username, phone, 'offline'],
            )
    elif user_type == 'merchant':
        existing = execute_fetchone('SELECT id FROM merchant WHERE user_profile_id = %s', [profile_id])
        if not existing:
            execute_write(
                '''
                INSERT INTO merchant (user_profile_id, merchant_name, phone, address, created_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ''',
                [profile_id, username, phone, '待填写'],
            )
    elif user_type == 'platform':
        existing = execute_fetchone('SELECT id FROM platform WHERE user_profile_id = %s', [profile_id])
        if not existing:
            execute_write(
                '''
                INSERT INTO platform (user_profile_id, platform_name, phone, created_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ''',
                [profile_id, username, phone],
            )


def cleanup_user_records(user_id):
    execute_non_query('DELETE FROM user_profile WHERE user_id = %s', [user_id])
    execute_non_query('DELETE FROM auth_user WHERE id = %s', [user_id])


def register(request):
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password')
        user_type = request.POST.get('user_type', 'customer')
        phone = (request.POST.get('phone', '') or '').strip()

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
            user_id = create_user_with_sql(username, password)
            logger.info(f"用户创建成功: {user_id}")

            profile_id = ensure_user_profile(user_id, user_type, phone)
            logger.info(f"用户资料处理成功: {profile_id}, 类型: {user_type}")

            ensure_detail_record(user_type=user_type, profile_id=profile_id, username=username, phone=phone)
            logger.info("类型记录创建完成")

            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'注册成功！欢迎{user_type}用户 {username}')
            else:
                messages.error(request, '自动登录失败，请手动登录')
                return redirect('login')

            return redirect('login')

        except Exception as e:
            logger.error(f"注册错误: {str(e)}")
            if 'user_id' in locals():
                cleanup_user_records(user_id)
            messages.error(request, f'注册失败: {str(e)}')
            return render(request, 'register.html')

    return render(request, 'register.html')


@require_GET
def check_username(request):
    username = (request.GET.get('username') or '').strip()
    if not username:
        return JsonResponse({'available': False, 'message': '用户名不能为空'}, status=400)
    exists = check_username_exists(username)
    return JsonResponse({'available': not exists})
