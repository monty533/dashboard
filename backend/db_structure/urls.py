from django.urls import path
from .nse import nse_file, nse_ucc_modify
from .bse import bse_ucc_modify
from .bse_starmf import bse_starmf_credentials_view, bse_starmf_file, bse_starmf_ucc_modify
from .ckyc import (
    ckyc_credentials_view, ckyc_file, ckyc_ucc_modify,
)
from .kra import kra_credentials_view, kra_file, kra_ucc_modify
from .cdsl import cdsl_ucc_modify, cdsl_credentials_view, cdsl_file, cdsl_upload_status
from .nsdl import nsdl_credentials_view, nsdl_file, nsdl_ucc_modify
from .mcx import mcx_credentials_view, mcx_file, mcx_ucc_modify
from .mse import mse_credentials_view, mse_file, mse_ucc_modify
from .client_api import client_me_view, register_view
from .dashboard import dashboard_log_view, dashboard_view
from .userdetails_api import UserDetailsAPIView
from .views import (
    bse_credentials_view,
    nse_credentials_view,
    login_view,
    logout_view,
    SchemaView,
    table_data_view,
    tables_view,
    users_list_view,
)

urlpatterns = [
    path('register/', register_view, name='register'),
    path('client/me/', client_me_view, name='client_me'),
    path('client/userupdatedata/', UserDetailsAPIView.as_view(), name='client_userupdatedata'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('dashboard/log/', dashboard_log_view, name='dashboard_log'),
    path('cdsl_ucc_modify/<str:clientcode>/', cdsl_ucc_modify, name='cdsl_ucc_modify'),
    path('cdsl_credentials/', cdsl_credentials_view, name='cdsl_credentials'),
    path('cdsl_upload/<int:upload_id>/status/', cdsl_upload_status, name='cdsl_upload_status'),
    path('cdsl_upload/<int:upload_id>/file/<str:kind>/', cdsl_file, name='cdsl_file'),
    path('bse_ucc_modify/<str:clientcode>/', bse_ucc_modify, name='bse_ucc_modify'),
    path('bse_starmf_ucc_modify/<str:clientcode>/', bse_starmf_ucc_modify, name='bse_starmf_ucc_modify'),
    path('bse_starmf_credentials/', bse_starmf_credentials_view, name='bse_starmf_credentials'),
    path('ckyc_credentials/', ckyc_credentials_view, name='ckyc_credentials'),
    path('ckyc_ucc_modify/<str:clientcode>/', ckyc_ucc_modify, name='ckyc_ucc_modify'),
    path('ckyc_file/<str:clientcode>/<str:kind>/', ckyc_file, name='ckyc_file'),
    path('kra_credentials/', kra_credentials_view, name='kra_credentials'),
    path('kra_ucc_modify/<str:clientcode>/', kra_ucc_modify, name='kra_ucc_modify'),
    path('kra_file/<str:clientcode>/<str:kind>/', kra_file, name='kra_file'),
    path('bse_starmf_file/<str:clientcode>/<str:kind>/', bse_starmf_file, name='bse_starmf_file'),
    path('login/',                         login_view,      name='login'),
    path('logout/',                        logout_view,     name='logout'),
    path('tables/',                        tables_view,     name='tables'),
    path('table/<str:table_name>/schema/', SchemaView.as_view(), name='table_schema'),
    path('table/<str:table_name>/data/',   table_data_view, name='table_data'),
    path('users/',                         users_list_view, name='users_list'),
    path('bse_credentials/',               bse_credentials_view, name='bse_credentials'),
    path('nse_credentials/',               nse_credentials_view, name='nse_credentials'),
    path('nse_ucc_modify/<str:clientcode>/', nse_ucc_modify, name='nse_ucc_modify'),
    path('nse_file/<str:clientcode>/<str:kind>/', nse_file, name='nse_file'),
    path('nsdl_ucc_modify/<str:clientcode>/', nsdl_ucc_modify, name='nsdl_ucc_modify'),
    path('nsdl_credentials/', nsdl_credentials_view, name='nsdl_credentials'),
    path('nsdl_file/<str:clientcode>/<str:kind>/', nsdl_file, name='nsdl_file'),
    path('mcx_ucc_modify/<str:clientcode>/', mcx_ucc_modify, name='mcx_ucc_modify'),
    path('mcx_credentials/', mcx_credentials_view, name='mcx_credentials'),
    path('mcx_file/<str:clientcode>/<str:kind>/', mcx_file, name='mcx_file'),
    path('mse_ucc_modify/<str:clientcode>/', mse_ucc_modify, name='mse_ucc_modify'),
    path('mse_credentials/', mse_credentials_view, name='mse_credentials'),
    path('mse_file/<str:clientcode>/<str:kind>/', mse_file, name='mse_file'),
]
