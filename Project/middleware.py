from django.contrib.auth import get_user_model
from django.utils import timezone

from Project.db_utils import execute_fetchone


class MultiSessionTokenMiddleware:
    """
    支持通过自定义 session token 进行多账号会话的中间件。
    如果请求头/查询参数/自定义 Cookie 中包含 token，则自动识别并注入 request.user。
    """

    COOKIE_NAME = "speedeats_session_token"
    HEADER_NAME = "HTTP_X_SESSION_TOKEN"
    QUERY_PARAM = "session_token"

    def __init__(self, get_response):
        self.get_response = get_response
        self.user_model = get_user_model()

    def __call__(self, request):
        token = self._extract_token(request)

        if token and not request.user.is_authenticated:
            session = self._get_active_session(token)
            user = self._load_user(session["user_id"]) if session else None

            if session and user:
                request.user = user
                request._cached_user = user  # noqa: SLF001
                request.multi_session_token = token
            else:
                request.invalid_multi_session_token = token

        response = self.get_response(request)

        if getattr(request, "invalid_multi_session_token", None):
            response.delete_cookie(self.COOKIE_NAME)

        return response

    def _get_active_session(self, token):
        if not token:
            return None

        query = """
            SELECT id, user_id
            FROM user_session
            WHERE session_token = %s
              AND is_active = 1
              AND expires_at > %s
            LIMIT 1
        """
        return execute_fetchone(query, [token, timezone.now()])

    def _load_user(self, user_id):
        if not user_id:
            return None

        query = """
            SELECT id,
                   password,
                   last_login,
                   is_superuser,
                   username,
                   first_name,
                   last_name,
                   email,
                   is_staff,
                   is_active,
                   date_joined
            FROM auth_user
            WHERE id = %s
        """
        record = execute_fetchone(query, [user_id])
        if not record:
            return None

        user = self.user_model(**record)
        user._state.adding = False  # type: ignore[attr-defined]
        user._state.db = "default"  # type: ignore[attr-defined]
        user.backend = "django.contrib.auth.backends.ModelBackend"
        return user

    def _extract_token(self, request):
        if hasattr(request, "multi_session_token"):
            return request.multi_session_token

        token = request.META.get(self.HEADER_NAME)
        if token:
            return token

        token = request.GET.get(self.QUERY_PARAM)
        if token:
            return token

        return request.COOKIES.get(self.COOKIE_NAME)
