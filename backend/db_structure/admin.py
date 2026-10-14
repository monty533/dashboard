from django.contrib import admin
from .models import (
    Cdsl, CdslCredentials, CdslIncomeRangeMaster, CdslStateCodeMaster,
    CdslNominee, CdslUpload, Mcx, McxCredentials,
    McxStateCityMaster, McxMaritalStatusMaster, McxIncomeRangeMaster,
    McxOccupationMaster, McxAccountTypeMaster, McxErrorCode, KraErrorCode,
    Mse, MseCredentials,
    MseAccountTypeMaster, MseIncomeRangeMaster, MseOccupationMaster,
    MseStateCodeMaster,
    UserProfile, ClientApiKey,
)

admin.site.register((Cdsl, CdslIncomeRangeMaster, CdslStateCodeMaster))
admin.site.register((
    Mcx,
    McxStateCityMaster,
    McxMaritalStatusMaster,
    McxIncomeRangeMaster,
    McxOccupationMaster,
    McxAccountTypeMaster,
    McxErrorCode,
    KraErrorCode,
    Mse,
    MseStateCodeMaster,
    MseIncomeRangeMaster,
    MseOccupationMaster,
    MseAccountTypeMaster,
))


@admin.register(McxCredentials)
class McxCredentialsAdmin(admin.ModelAdmin):
    list_display = ('user', 'environment', 'member_id', 'updated_at')
    exclude = ('api_key', 'aes_key')


@admin.register(MseCredentials)
class MseCredentialsAdmin(admin.ModelAdmin):
    list_display = ('user', 'environment', 'login_id', 'updated_at')
    exclude = ('password',)


@admin.register(CdslNominee)
class CdslNomineeAdmin(admin.ModelAdmin):
    list_display = ('client', 'sequence', 'first_name', 'share')
    raw_id_fields = ('client',)


@admin.register(CdslCredentials)
class CdslCredentialsAdmin(admin.ModelAdmin):
    list_display = ('user', 'DPID', 'UserID')
    exclude = ('Password', 'AES_key')  # Manage secrets through the company's Credentials page.


@admin.register(CdslUpload)
class CdslUploadAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'client', 'status', 'acknowledgment_id', 'created_at')
    list_filter = ('status',)
    search_fields = ('client__clientcode', 'acknowledgment_id')
    readonly_fields = ('user', 'client', 'batch_number', 'filename', 'row_count', 'response', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'company_name', 'phone', 'updated_at')
    search_fields = ('user__username', 'user__email', 'company_name', 'phone')
    raw_id_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ClientApiKey)
class ClientApiKeyAdmin(admin.ModelAdmin):
    list_display = ('prefix', 'user', 'is_active', 'expires_at', 'last_used_at')
    list_filter = ('is_active',)
    search_fields = ('prefix', 'user__username', 'user__email')
    readonly_fields = ('user', 'prefix', 'key_hash', 'created_at', 'updated_at', 'last_used_at')
    fields = (
        'user', 'prefix', 'key_hash', 'is_active',
        'expires_at', 'revoked_at', 'last_used_at', 'created_at', 'updated_at',
    )

    def has_add_permission(self, request):
        # Plain API keys are returned only by the registration flow.
        return False
