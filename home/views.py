from django.shortcuts import render, redirect
from django.views import View


class HomeView(View):
    def get(self, request):
        return render(request, 'home.html')


def redirect_to_login(request):
    """重定向到登录页面"""
    return redirect('login')