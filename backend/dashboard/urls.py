"""
URL configuration for dashboard project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    re_path(
        r'^static/(?P<path>bse_data/[A-Za-z0-9_-][A-Za-z0-9_.-]*/bse_(?:request|response)\.txt)$',
        serve,
        {'document_root': settings.BASE_DIR / 'static'},
        name='bse_static_file',
    ),
    re_path(
        r'^static/(?P<path>nsdl_data/[A-Za-z0-9_.-]+/nsdl_(?:request\.txt|request\.csv|request\.zip|response\.txt))$',
        serve,
        {'document_root': settings.BASE_DIR / 'static'},
        name='nsdl_static_file',
    ),
    re_path(
        r'^static/(?P<path>cdsl_data/[A-Za-z0-9_-][A-Za-z0-9_.-]*/(?:request|response)\.txt)$',
        serve,
        {'document_root': settings.BASE_DIR / 'static'},
        name='cdsl_static_file',
    ),
    path('admin/', admin.site.urls),
    path('api/', include('db_structure.urls')),
]
