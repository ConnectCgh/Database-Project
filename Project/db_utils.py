from django.db import connection


def dictfetchall(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def dictfetchone(cursor):
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


def execute_fetchall(query, params=None):
    with connection.cursor() as cursor:
        cursor.execute(query, params or [])
        return dictfetchall(cursor)


def execute_fetchone(query, params=None):
    with connection.cursor() as cursor:
        cursor.execute(query, params or [])
        return dictfetchone(cursor)


def execute_write(query, params=None):
    with connection.cursor() as cursor:
        cursor.execute(query, params or [])
        return cursor.lastrowid


def execute_non_query(query, params=None):
    with connection.cursor() as cursor:
        cursor.execute(query, params or [])
        return cursor.rowcount


def quote_table(name):
    return connection.ops.quote_name(name)


ALLOWED_USER_ENTITY_TABLES = {'customer', 'merchant', 'platform', 'rider'}


def get_entity_by_user(table_name, user_id):
    if table_name not in ALLOWED_USER_ENTITY_TABLES:
        raise ValueError(f'Unsupported entity table: {table_name}')
    table = quote_table(table_name)
    query = f'''
        SELECT t.*
        FROM {table} t
        JOIN user_profile up ON t.user_profile_id = up.id
        WHERE up.user_id = %s
    '''
    return execute_fetchone(query, [user_id])


def get_customer_by_user(user_id):
    return get_entity_by_user('customer', user_id)


def get_merchant_by_user(user_id):
    return get_entity_by_user('merchant', user_id)


def get_platform_by_user(user_id):
    return get_entity_by_user('platform', user_id)


def get_rider_by_user(user_id):
    return get_entity_by_user('rider', user_id)
