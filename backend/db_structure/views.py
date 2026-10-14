from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.conf import settings
from django.db import DatabaseError, connection, models
from django.db.models import OuterRef, Subquery
from django.utils.timezone import localtime
import logging
import re
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.throttling import AnonRateThrottle
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from .models import (
    Cdsl,
    CdslUpload,
    CdslStateCodeMaster,
    CdslIncomeRangeMaster,
    BseCredentials,
    BseStarMf,
    BseStarMfDependencyMaster,
    BseStarMfGenderMaster,
    BseStarMfStateCodeMaster,
    BseStarMfTaxStatusMaster,
    BseIncomeRangeMaster,
    NseCredentials,
    NseIncomeRangeMaster,
    NseMaritalStatusMaster,
    NseOccupationMaster,
    NseStateCodeMaster,
    NsdlIncomeRangeMaster,
    NsdlAccountTypeMaster,
    NsdlCountryMaster,
    NsdlGenderMaster,
    NsdlOccupationMaster,
    NsdlRelationMaster,
    NsdlStateCodeMaster,
    Nsdl,
    Mcx,
    McxAccountTypeMaster,
    McxCredentials,
    McxErrorCode,
    McxGenderMaster,
    McxIncomeRangeMaster,
    McxMaritalStatusMaster,
    McxOccupationMaster,
    McxStateCityMaster,
    Mse,
    MseAccountTypeMaster,
    MseIncomeRangeMaster,
    MseOccupationMaster,
    MseStateCodeMaster,
    UserDetails,
    SchemaColumnMetadata,
    Bse,
    Nse,
    BSE_MANDATORY_COLUMNS,
    BSE_STAR_MF_MANDATORY_COLUMNS,
    CDSL_MANDATORY_COLUMNS,
    Ckyc,
    ClientApiKey,
    CkycStateCodeMaster,
    CKYC_MANDATORY_COLUMNS,
    Kra,
    KraErrorCode,
    KraGenderMaster,
    KraMaritalStatusMaster,
    KraStatusMaster,
    KRA_COLUMN_MAX_LENGTHS,
    KRA_MANDATORY_COLUMNS,
    MCX_MANDATORY_COLUMNS,
    NSE_MANDATORY_COLUMNS,
    NSDL_MANDATORY_COLUMNS,
)
from .nsdl_fields import nsdl_payload_metadata

logger = logging.getLogger(__name__)

# ── Table Registry ────────────────────────────────────────────────────────────
TABLE_MAP = {
    'userdetails': UserDetails,
    'bse': Bse,
    'bse_star_mf': BseStarMf,
    'bse_star_mf_dependency_master': BseStarMfDependencyMaster,
    'bse_star_mf_gender_master': BseStarMfGenderMaster,
    'bse_star_mf_state_code_master': BseStarMfStateCodeMaster,
    'bse_star_mf_tax_status_master': BseStarMfTaxStatusMaster,
    'cdsl': Cdsl,
    'ckyc': Ckyc,
    'ckyc_state_code_master': CkycStateCodeMaster,
    'kra': Kra,
    'kra_error_code': KraErrorCode,
    'kra_status_master': KraStatusMaster,
    'kra_marital_status_master': KraMaritalStatusMaster,
    'kra_gender_master': KraGenderMaster,
    'cdsl_state_code_master': CdslStateCodeMaster,
    'cdsl_income_range_master': CdslIncomeRangeMaster,
    'nse': Nse,
    'nsdl': Nsdl,
    'nse_state_code_master': NseStateCodeMaster,
    'nse_marital_status_master': NseMaritalStatusMaster,
    'nse_occupation_master': NseOccupationMaster,
    'nse_income_range_master': NseIncomeRangeMaster,
    'bse_income_range_master': BseIncomeRangeMaster,
    'nsdl_state_code_master': NsdlStateCodeMaster,
    'nsdl_income_range_master': NsdlIncomeRangeMaster,
    'nsdl_account_type_master': NsdlAccountTypeMaster,
    'nsdl_country_master': NsdlCountryMaster,
    'nsdl_gender_master': NsdlGenderMaster,
    'nsdl_occupation_master': NsdlOccupationMaster,
    'nsdl_relation_master': NsdlRelationMaster,
    'mcx': Mcx,
    'mcx_state_city_master': McxStateCityMaster,
    'mcx_marital_status_master': McxMaritalStatusMaster,
    'mcx_gender_master': McxGenderMaster,
    'mcx_income_range_master': McxIncomeRangeMaster,
    'mcx_occupation_master': McxOccupationMaster,
    'mcx_account_type_master': McxAccountTypeMaster,
    'mcx_error_code': McxErrorCode,
    'mse': Mse,
    'mse_state_code_master': MseStateCodeMaster,
    'mse_income_range_master': MseIncomeRangeMaster,
    'mse_occupation_master': MseOccupationMaster,
    'mse_account_type_master': MseAccountTypeMaster,
}

TABLE_COLUMN_ALIASES = {
    UserDetails: {
        'name': 'aadhaar_name',
    },
}

CREDENTIAL_FIELDS = ['MemberCode', 'UserID', 'Password']
CONDITIONAL_PARAMETER_OPTIONS = ('individual', 'jointholder')
CONDITIONAL_PARAMETER_OPTIONS_BY_COLUMN = {
    'account_holder_type': CONDITIONAL_PARAMETER_OPTIONS,
    'modeoftrading': ('offline', 'online'),
    'mode_of_account': ('N', 'M'),
    'transaction_type': ('account_opening', 'segment_addition', 'modification'),
    'activestatus': ('A', 'I'),
    'bse_cash': ('true', 'false'),
    'bse_currency': ('true', 'false'),
    'bse_fo': ('true', 'false'),
    'bse_slbm': ('true', 'false'),
    'mcx': ('true', 'false'),
    'nse_cash': ('true', 'false'),
    'nse_currency': ('true', 'false'),
    'nse_fo': ('true', 'false'),
    'nse_slbm': ('true', 'false'),
    'nominee_check': ('yes', 'no'),
}

# ── Type Mappings ─────────────────────────────────────────────────────────────
FIELD_TYPE_MAP = {
    'str':      'VARCHAR(255)',
    'text':     'TEXT',
    'int':      'INT',
    'bigint':   'BIGINT',
    'float':    'DOUBLE',
    'bool':     'TINYINT(1)',
    'date':     'DATE',
    'datetime': 'DATETIME(6)',
}

MYSQL_TO_LABEL = {
    'varchar':   'str',
    'text':      'text',
    'longtext':  'text',
    'mediumtext': 'text',
    'int':       'int',
    'bigint':    'bigint',
    'double':    'float',
    'float':     'float',
    'decimal':   'float',
    'tinyint':   'bool',
    'bool':      'bool',
    'date':      'date',
    'datetime':  'datetime',
}

def _field_requirement(model, column_name, nullable=True):
    mandatory = (
        BSE_MANDATORY_COLUMNS if model is Bse else
        BSE_STAR_MF_MANDATORY_COLUMNS if model is BseStarMf else
        CDSL_MANDATORY_COLUMNS if model is Cdsl else
        CKYC_MANDATORY_COLUMNS if model is Ckyc else
        KRA_MANDATORY_COLUMNS if model is Kra else
        MCX_MANDATORY_COLUMNS if model is Mcx else
        NSE_MANDATORY_COLUMNS if model is Nse else
        NSDL_MANDATORY_COLUMNS if model is Nsdl else
        set()
    )
    if model in {Bse, BseStarMf, Nse, Nsdl, Cdsl, Ckyc, CkycStateCodeMaster, Kra, KraStatusMaster, KraMaritalStatusMaster, KraGenderMaster, Mcx, UserDetails, NseStateCodeMaster,
                 NseMaritalStatusMaster, NseOccupationMaster, NseIncomeRangeMaster, BseIncomeRangeMaster,
                 CdslStateCodeMaster, CdslIncomeRangeMaster,
                 NsdlStateCodeMaster, NsdlIncomeRangeMaster,
                 NsdlOccupationMaster, NsdlRelationMaster, NsdlAccountTypeMaster,
                 NsdlCountryMaster, NsdlGenderMaster,
                 McxStateCityMaster,
                 McxMaritalStatusMaster, McxGenderMaster, McxIncomeRangeMaster,
                 McxOccupationMaster, McxAccountTypeMaster,
                 McxErrorCode, Mse, MseStateCodeMaster, MseIncomeRangeMaster,
                 MseOccupationMaster, MseAccountTypeMaster, KraErrorCode,
                 BseStarMfDependencyMaster, BseStarMfGenderMaster,
                 BseStarMfStateCodeMaster,
                 BseStarMfTaxStatusMaster}:
        return 'mandatory' if column_name in mandatory or not nullable else 'optional'
    return None


def _schema_column_metadata(db_table):
    return {
        column_name: conditional_parameter
        for column_name, conditional_parameter in SchemaColumnMetadata.objects.filter(
            table_name=db_table,
        ).values_list('column_name', 'conditional_parameter')
    }


def _conditional_parameter_value(value, column_name=None):
    value = str(value or '').strip()
    options = CONDITIONAL_PARAMETER_OPTIONS_BY_COLUMN.get(
        str(column_name or '').lower(),
        CONDITIONAL_PARAMETER_OPTIONS,
    )
    if value and value not in options:
        return None, (
            f'Unknown conditional parameter "{value}". Valid options: '
            f'{list(options)}'
        )
    return value, None


def _save_schema_column_metadata(db_table, column_name, conditional_parameter):
    if conditional_parameter:
        SchemaColumnMetadata.objects.update_or_create(
            table_name=db_table,
            column_name=column_name,
            defaults={'conditional_parameter': conditional_parameter},
        )
    else:
        SchemaColumnMetadata.objects.filter(
            table_name=db_table,
            column_name=column_name,
        ).delete()


def _model_field_for_column(model, column_name):
    """Resolve a schema column to a model field, including custom db_column names."""
    return next(
        (
            field for field in model._meta.get_fields()
            if field.concrete and (field.name == column_name or field.column == column_name)
        ),
        None,
    )


INTROSPECTION_TYPE_LABELS = {
    'AutoField': 'int',
    'BigAutoField': 'bigint',
    'BigIntegerField': 'bigint',
    'BooleanField': 'bool',
    'CharField': 'str',
    'DateField': 'date',
    'DateTimeField': 'datetime',
    'DecimalField': 'float',
    'FloatField': 'float',
    'IntegerField': 'int',
    'PositiveBigIntegerField': 'bigint',
    'PositiveIntegerField': 'int',
    'SmallAutoField': 'int',
    'SmallIntegerField': 'int',
    'TextField': 'text',
}

LABEL_TO_DB_TYPE = {
    'str': 'varchar',
    'text': 'text',
    'int': 'int',
    'bigint': 'bigint',
    'float': 'double',
    'bool': 'tinyint',
    'date': 'date',
    'datetime': 'datetime',
}

# ``UserDetails`` is a legacy table and its editable values are treated as
# strings by the schema editor. Keep the primary key and foreign-key columns
# as their real numeric types because those columns cannot be edited.
USERDETAILS_STRUCTURAL_COLUMNS = frozenset({'id', 'user_id'})


def _schema_display_label(model, column_name, actual_label):
    """Return the type label shown by the schema editor."""
    column = str(column_name).lower()
    if model is UserDetails and column not in USERDETAILS_STRUCTURAL_COLUMNS:
        return 'str'
    if model is Kra and column != 'id':
        # KRA values are edited as strings even when TEXT is used physically
        # in MySQL to avoid the 65,535-byte row-size limit.
        return 'str'
    return actual_label


def _schema_display_max_length(model, column_name, actual_label, max_length):
    """Return the configured business length shown by the schema editor."""
    column = str(column_name)
    if model is Kra and column != 'id':
        return KRA_COLUMN_MAX_LENGTHS.get(column, max_length)
    if (
        model is UserDetails
        and column.lower() not in USERDETAILS_STRUCTURAL_COLUMNS
        and actual_label == 'text'
    ):
        return 65535
    return max_length


def _database_description(db_table):
    """Read database columns through Django's backend introspection API."""
    with connection.cursor() as cursor:
        return connection.introspection.get_table_description(cursor, db_table)


def _model_database_columns(model, db_table, descriptions=None):
    """Return only columns declared by the model and present in the database."""
    if descriptions is None:
        descriptions = _database_description(db_table)
    database_columns = {
        description.name
        for description in descriptions
    }
    return {
        field.column
        for field in model._meta.get_fields()
        if field.concrete and field.column in database_columns
    }


def _description_label(description):
    field_type = connection.introspection.get_field_type(
        description.type_code,
        description,
    )
    return INTROSPECTION_TYPE_LABELS.get(field_type, field_type.lower())


def _schema_field_for_sql_type(
    model,
    field_name,
    sql_type,
    *,
    null=True,
    default=models.NOT_PROVIDED,
    db_default=models.NOT_PROVIDED,
    template=None,
):
    """Build a temporary Django field for a dynamic database column."""
    normalized = sql_type.upper()
    if normalized.startswith('VARCHAR'):
        field_class = models.CharField
        match = re.search(r'\((\d+)\)', normalized)
        max_length = int(match.group(1)) if match else 255
    elif normalized.startswith(('TEXT', 'LONGTEXT', 'MEDIUMTEXT')):
        field_class = models.TextField
        max_length = None
    elif normalized.startswith('BIGINT'):
        field_class = models.BigIntegerField
        max_length = None
    elif normalized.startswith(('INT', 'SMALLINT')):
        field_class = models.IntegerField
        max_length = None
    elif normalized.startswith(('DOUBLE', 'FLOAT', 'DECIMAL')):
        field_class = models.FloatField
        max_length = None
    elif normalized.startswith('TINYINT'):
        field_class = models.BooleanField
        max_length = None
    elif normalized.startswith('DATETIME'):
        field_class = models.DateTimeField
        max_length = None
    elif normalized.startswith('DATE'):
        field_class = models.DateField
        max_length = None
    else:
        field_class = models.CharField
        max_length = 255

    kwargs = {'null': null}
    if max_length is not None:
        kwargs['max_length'] = max_length
    if default is not models.NOT_PROVIDED:
        kwargs['default'] = default
    if db_default is not models.NOT_PROVIDED:
        kwargs['db_default'] = models.Value(db_default)

    field = field_class(**kwargs)
    field.set_attributes_from_name(field_name)
    field.model = model

    if template is not None:
        field.unique = template.unique
        field.db_index = template.db_index
        field.db_column = template.db_column or field.db_column

    return field


def _temporary_schema_field(model, column_name, info):
    """Build a Django field descriptor for a database-only schema column."""
    data_type = info['data_type'].lower()
    sql_type = (
        f'VARCHAR({info["max_length"] or 255})'
        if data_type == 'varchar'
        else data_type.upper()
    )
    db_default = info['default'] if info['default'] is not None else models.NOT_PROVIDED
    return _schema_field_for_sql_type(
        model,
        column_name,
        sql_type,
        null=info['nullable'],
        db_default=db_default,
    )


def _existing_schema_field(model, field_name, db_column, info):
    """Describe a live column while retaining model-level indexes."""
    field = _temporary_schema_field(model, db_column, info)
    model_field = _model_field_for_column(model, field_name)
    if model_field is not None:
        field.set_attributes_from_name(model_field.name)
        field.db_column = model_field.db_column or db_column
        field.unique = model_field.unique
        field.db_index = model_field.db_index
    return field


def _column_info(db_table, column_name):
    """Return column information using Django database introspection."""
    description = next(
        (item for item in _database_description(db_table) if item.name == column_name),
        None,
    )
    if description is None:
        return None

    label = _description_label(description)
    return {
        'data_type': LABEL_TO_DB_TYPE.get(label, label),
        'max_length': description.internal_size if label in {'str', 'text'} else None,
        'nullable': bool(description.null_ok),
        'default': description.default,
    }


def _sql_type_from_request(data):
    data_type = data.get('data_type') or data.get('new_type') or ''
    data_type = data_type.strip().lower()
    max_length = data.get('max_length')

    if not data_type:
        return None, None, 'data_type is required.'

    if data_type not in FIELD_TYPE_MAP:
        return None, None, f'Unknown type "{data_type}". Valid types: {list(FIELD_TYPE_MAP.keys())}'

    if data_type == 'str':
        if max_length in (None, ''):
            max_length = 255
        else:
            try:
                max_length = int(max_length)
            except (TypeError, ValueError):
                return None, None, 'max_length must be a number.'

            if max_length < 1 or max_length > 65535:
                return None, None, 'max_length must be between 1 and 65535.'

        return f'VARCHAR({max_length})', max_length, None

    if max_length not in (None, ''):
        return None, None, 'max_length can only be used with str/VARCHAR columns.'

    return FIELD_TYPE_MAP[data_type], None, None


def _empty_value_for_sql_type(sql_type):
    normalized = sql_type.upper()
    if normalized.startswith(('INT', 'BIGINT', 'DOUBLE', 'FLOAT', 'DECIMAL')):
        return '0'
    if normalized.startswith('TINYINT'):
        return '0'
    if normalized.startswith('DATE') and not normalized.startswith('DATETIME'):
        return '1970-01-01'
    if normalized.startswith('DATETIME'):
        return '1970-01-01 00:00:00'
    return ''


def _model_row_payload(row):
    payload = {}
    for field in row._meta.get_fields():
        if not getattr(field, 'concrete', False):
            continue
        value = getattr(row, field.name)
        if value is None:
            payload[field.name] = ''
        elif hasattr(value, 'strftime'):
            payload[field.name] = localtime(value).strftime('%Y-%m-%d %H:%M:%S')
        else:
            payload[field.name] = str(value)
    return payload


# ── AUTHENTICATION VIEWS ──────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def login_view(request):
    """
    POST /api/login/
    Body: { "email": "...", "password": "..." }
    """
    email = request.data.get('email', '')
    password = request.data.get('password', '')
    if not isinstance(email, str) or not isinstance(password, str):
        return Response({'error': 'Email and password must be strings.'}, status=400)
    email = email.strip()

    if not email or not password:
        return Response(
            {'error': 'Email and password are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user_obj = User.objects.get(email__iexact=email)
    except (User.DoesNotExist, User.MultipleObjectsReturned):
        try:
            user_obj = User.objects.get(username__iexact=email)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return Response(
                {'error': 'Invalid email or password.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

    user = authenticate(request, username=user_obj.username, password=password)
    if user is None:
        logger.warning("Failed login attempt")
        return Response(
            {'error': 'Invalid email or password.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token, _ = Token.objects.get_or_create(user=user)
    role = 'admin' if (user.is_staff or user.is_superuser) else 'user'
    logger.info("User logged in: id=%s role=%s", user.id, role)
    return Response({
        'token': token.key,
        'username': user.username,
        'email': user.email,
        'role': role,
    })


@api_view(['POST'])
def logout_view(request):
    """POST /api/logout/"""
    if hasattr(request.user, 'auth_token'):
        request.user.auth_token.delete()
    logger.info("User logged out: id=%s", request.user.id)
    return Response({'message': 'Logged out successfully.'})


@api_view(['GET'])
def users_list_view(request):
    """GET /api/users/ — list all registered users (admin only)"""
    if not (request.user.is_staff or request.user.is_superuser):
        logger.warning("Permission denied for users list: user_id=%s", request.user.id)
        return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    active_key = ClientApiKey.objects.filter(
        user_id=OuterRef('pk'),
        is_active=True,
        revoked_at__isnull=True,
    ).order_by('-created_at')
    users_qs = User.objects.filter(
        is_staff=False,
        is_superuser=False,
    ).annotate(
        api_key_prefix=Subquery(active_key.values('prefix')[:1]),
        api_key_hash=Subquery(active_key.values('key_hash')[:1]),
    ).order_by('id').values(
        'id', 'username', 'email', 'is_staff', 'is_active', 'date_joined',
        'profile__company_name', 'api_key_prefix', 'api_key_hash',
    )
    data = []
    for user in users_qs:
        prefix = user['api_key_prefix'] or ''
        key_hash = user['api_key_hash'] or ''
        data.append({
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'company_name': user['profile__company_name'],
            'role': 'admin' if user['is_staff'] else 'user',
            'is_active': user['is_active'],
            'date_joined': localtime(user['date_joined']).strftime('%Y-%m-%d %H:%M:%S') if user['date_joined'] else '',
            # The original secret is intentionally not stored. The authentication
            # layer accepts prefix.key_hash for privileged admin requests.
            'api_key_prefix': prefix,
            'api_key': f'{prefix}.{key_hash}' if prefix and key_hash else '',
            'api_key_available': bool(prefix and key_hash),
        })
    return Response({'users': data})


def _requested_company_user(request):
    if request.user.is_staff or request.user.is_superuser:
        user_id = request.GET.get('user_id')
        if not user_id and request.method != 'GET':
            user_id = request.data.get('user_id')
        if user_id:
            try:
                return User.objects.get(id=user_id, is_staff=False, is_superuser=False)
            except (User.DoesNotExist, ValueError, TypeError, OverflowError):
                return None
        return request.user
    return request.user


@api_view(['GET', 'POST'])
def bse_credentials_view(request):
    """
    GET  /api/bse-credentials/?user_id=...
    POST /api/bse-credentials/
    Body: { "user_id": 2, "MemberCode": "...", "UserID": "...", "Password": "..." }
    """
    company_user = _requested_company_user(request)
    if company_user is None:
        return Response({'error': 'Company not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        credential = BseCredentials.objects.filter(user=company_user, type='bse').first()
        return Response({
            'user_id': company_user.id,
            'company': company_user.username,
            'credentials': {
                'MemberCode': credential.MemberCode if credential else '',
                'UserID': credential.UserID if credential else '',
                'Password': (credential.Password or '') if credential else '',
            },
        })

    payload = {
        field: request.data.get(field, '') or ''
        for field in CREDENTIAL_FIELDS
    }
    if not payload['Password']:
        payload.pop('Password')
    logger.info(
        "Saving BSE credentials for user_id=%s member_code=%s user_id_value=%s",
        company_user.id,
        payload.get('MemberCode'),
        payload.get('UserID'),
    )
    credential, _ = BseCredentials.objects.update_or_create(
        user=company_user,
        type='bse',
        defaults=payload,
    )
    return Response({
        'success': True,
        'id': credential.id,
        'user_id': company_user.id,
        'company': company_user.username,
        'type': credential.type,
        'credentials': {
            'MemberCode': credential.MemberCode or '',
            'UserID': credential.UserID or '',
            'Password': credential.Password or '',
        },
    })

@api_view(['GET', 'POST'])
def nse_credentials_view(request):
    """
    GET  /api/nse_credentials/?user_id=...
    POST /api/nse_credentials/

    Body:
    {
        "user_id": 2,
        "Username": "...",
        "Password": "..."
    }
    """
    company_user = _requested_company_user(request)
    if company_user is None:
        return Response(
            {'error': 'Company not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # GET - fetch existing NSE credentials
    if request.method == 'GET':
        credential = NseCredentials.objects.filter(
            user=company_user
        ).first()

        return Response({
            'user_id': company_user.id,
            'company': company_user.username,
            'credentials': {
                'username': credential.username if credential else '',
                'password': credential.password if credential else '',
                'apiName': credential.apiName if credential else '',
            },
        })

    # POST - create/update NSE credentials
    payload = {
        'username': request.data.get('username', ''),
        'password': request.data.get('password', ''),
        'apiName': request.data.get('apiName', ''),
    }

    if not payload['password']:
        payload.pop('password')
    logger.info(
        "Saving NSE credentials for user_id=%s username=%s api_name=%s",
        company_user.id,
        payload['username'],
        payload['apiName'],
    )

    credential, _ = NseCredentials.objects.update_or_create(
        user=company_user,
        defaults=payload,
    )

    return Response({
        'success': True,
        'id': credential.id,
        'user_id': company_user.id,
        'company': company_user.username,
        'credentials': {
            'username': credential.username or '',
            'password': credential.password or '',
            'apiName': credential.apiName or '',
        },
    })


@api_view(['GET'])
def tables_view(request):
    """GET /api/tables/ — list available tables."""
    tables = sorted(TABLE_MAP) if request.user.is_staff or request.user.is_superuser else ['userdetails']
    return Response({'tables': tables})


# ── SCHEMA & DATA VIEWS ───────────────────────────────────────────────────────
class SchemaView(APIView):
    """Read and safely manage the schema for a registered table."""

    @staticmethod
    def _text(value, default=''):
        return default if value is None else str(value).strip()

    def _context(self, request, table_name):
        table_key = self._text(table_name).lower()
        is_admin = request.user.is_staff or request.user.is_superuser
        can_read_dashboard_schema = request.method == 'GET' and table_key == 'userdetails'

        if not (is_admin or can_read_dashboard_schema):
            message = (
                'Permission denied.' if request.method == 'GET'
                else 'Permission denied. Only admins can modify table schema.'
            )
            return None, Response({'error': message}, status=status.HTTP_403_FORBIDDEN)

        model = TABLE_MAP.get(table_key)
        if not model:
            return None, Response(
                {'error': f'Table "{table_name}" not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method != 'GET' and not settings.ALLOW_SCHEMA_MUTATIONS:
            return None, Response(
                {'error': 'Schema editing is disabled in this environment.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        return (model, model._meta.db_table), None

    @staticmethod
    def _schema_fields(model, db_table):
        column_metadata = _schema_column_metadata(db_table)
        descriptions = _database_description(db_table)
        model_database_columns = _model_database_columns(model, db_table, descriptions)
        descriptions = [
            description
            for description in descriptions
            if description.name in model_database_columns
        ]
        is_nsdl = model is Nsdl
        if descriptions:
            fields = []
            for description in descriptions:
                actual_label = _description_label(description)
                label = _schema_display_label(model, description.name, actual_label)
                field = {
                    'name': description.name,
                    'db_type': LABEL_TO_DB_TYPE.get(label, label),
                    'label': label,
                    'max_length': _schema_display_max_length(
                        model,
                        description.name,
                        actual_label,
                        description.internal_size if actual_label in {'str', 'text'} else None,
                    ),
                    'nullable': bool(description.null_ok),
                    'default': description.default,
                    'requirement': _field_requirement(model, description.name, description.null_ok),
                    'conditional_parameter': column_metadata.get(description.name, ''),
                }
                if is_nsdl:
                    field.update(nsdl_payload_metadata(description.name))
                fields.append(field)
        else:
            fields = []
            for field in model._meta.get_fields():
                if not field.concrete or field.column not in model_database_columns:
                    continue
                schema_field = {
                    'name': field.name,
                    'db_type': field.db_type(connection),
                    'label': _schema_display_label(
                        model,
                        field.column,
                        (
                            'bigint' if field.primary_key else
                            'int' if field.is_relation else
                            'text' if isinstance(field, models.TextField) else
                            'str'
                        ),
                    ),
                    'max_length': getattr(field, 'max_length', None),
                    'nullable': field.null,
                    'default': field.default if field.default is not models.NOT_PROVIDED else None,
                    'requirement': _field_requirement(model, field.name, field.null),
                    'conditional_parameter': column_metadata.get(field.column, ''),
                }
                if is_nsdl:
                    schema_field.update(nsdl_payload_metadata(field.name))
                fields.append(schema_field)

        if model is NseStateCodeMaster:
            for field in fields:
                if field['name'] == 'state_name' and field['db_type'] == 'text':
                    field['value_max_length'] = field['max_length']

        return fields

    def get(self, request, table_name):
        context, error = self._context(request, table_name)
        if error:
            return error

        model, db_table = context
        return Response({
            'table': db_table,
            'model_columns': [
                field.column
                for field in model._meta.get_fields()
                if field.concrete
            ],
            'fields': self._schema_fields(model, db_table),
            'valid_types': list(FIELD_TYPE_MAP),
            'conditional_parameters': list(CONDITIONAL_PARAMETER_OPTIONS),
            'conditional_parameters_by_column': {
                column: list(options)
                for column, options in CONDITIONAL_PARAMETER_OPTIONS_BY_COLUMN.items()
            },
        })

    def delete(self, request, table_name):
        context, error = self._context(request, table_name)
        if error:
            return error

        model, db_table = context
        field_name = self._text(
            request.data.get('field') or request.query_params.get('field')
        )
        if not field_name:
            return Response({'error': '"field" is required.'}, status=status.HTTP_400_BAD_REQUEST)

        field = _model_field_for_column(model, field_name)
        db_column = field.db_column or field.column if field else field_name
        pk_column = model._meta.pk.db_column or model._meta.pk.column

        if (field and field.primary_key) or field_name == model._meta.pk.name or db_column == pk_column:
            return Response({'error': 'Primary key column cannot be deleted.'}, status=status.HTTP_400_BAD_REQUEST)

        if field and field.is_relation:
            return Response({'error': 'Relationship columns cannot be deleted.'}, status=status.HTTP_400_BAD_REQUEST)

        info = _column_info(db_table, db_column)
        if not info:
            return Response(
                {'error': f'Column "{field_name}" not found in database.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            schema_field = field or _temporary_schema_field(model, db_column, info)
            with connection.schema_editor() as schema_editor:
                schema_editor.remove_field(model, schema_field)

            SchemaColumnMetadata.objects.filter(
                table_name=db_table,
                column_name=db_column,
            ).delete()
            return Response({'success': True, 'table': db_table, 'field': field_name})
        except Exception:
            logger.exception(
                'Failed to delete schema column: table=%s field=%s user_id=%s',
                db_table,
                field_name,
                request.user.id,
            )
            return Response(
                {'error': 'Schema change failed. Check the column definition and server logs.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def post(self, request, table_name):
        context, error = self._context(request, table_name)
        if error:
            return error

        model, db_table = context
        column_name = self._text(request.data.get('field'))
        requirement = self._text(request.data.get('requirement'), 'optional').lower()

        if not column_name:
            return Response({'error': 'Column name is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if model is UserDetails:
            column_name = column_name.lower()

        conditional_parameter, conditional_error = _conditional_parameter_value(
            request.data.get('conditional_parameter'),
            column_name,
        )

        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', column_name):
            return Response(
                {'error': 'Column name can only contain letters, numbers, and underscore, and cannot start with a number.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if _column_info(db_table, column_name):
            return Response(
                {'error': f'Column "{column_name}" already exists.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if requirement not in {'mandatory', 'optional'}:
            return Response({'error': 'Requirement must be mandatory or optional.'}, status=status.HTTP_400_BAD_REQUEST)
        if conditional_error:
            return Response({'error': conditional_error}, status=status.HTTP_400_BAD_REQUEST)

        sql_type, max_length, error_msg = _sql_type_from_request(request.data)
        if error_msg:
            return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

        has_default = bool(request.data.get('has_default'))
        default_value = request.data.get('default_value')
        if has_default and sql_type.upper() in {'TEXT', 'LONGTEXT', 'MEDIUMTEXT'}:
            return Response({'error': 'Default value is not supported for text columns.'}, status=status.HTTP_400_BAD_REQUEST)

        # A mandatory column without a user default needs a one-time value
        # while existing rows are brought into compliance. Django removes
        # this temporary default after adding the column.
        field_default = (
            _empty_value_for_sql_type(sql_type)
            if requirement == 'mandatory' and not has_default
            else models.NOT_PROVIDED
        )
        db_default = (
            default_value if has_default and default_value is not None
            else models.NOT_PROVIDED
        )
        schema_field = _schema_field_for_sql_type(
            model,
            column_name,
            sql_type,
            null=requirement == 'optional',
            default=field_default,
            db_default=db_default,
        )

        try:
            with connection.schema_editor() as schema_editor:
                schema_editor.add_field(model, schema_field)

            logger.info(
                'Schema column added: table=%s field=%s type=%s requirement=%s user_id=%s',
                db_table,
                column_name,
                sql_type,
                requirement,
                request.user.id,
            )
            _save_schema_column_metadata(db_table, column_name, conditional_parameter)
            return Response({
                'success': True,
                'table': db_table,
                'field': column_name,
                'sql_type': sql_type,
                'max_length': max_length,
                'requirement': requirement,
                'conditional_parameter': conditional_parameter,
                'default': request.data.get('default_value') if request.data.get('has_default') else None,
            }, status=status.HTTP_201_CREATED)
        except Exception:
            logger.exception(
                'Failed to add schema column: table=%s field=%s user_id=%s',
                db_table,
                column_name,
                request.user.id,
            )
            return Response(
                {'error': 'Schema change failed. Check the column definition and server logs.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def patch(self, request, table_name):
        context, error = self._context(request, table_name)
        if error:
            return error

        model, db_table = context
        field_name = self._text(request.data.get('field'))
        new_type = self._text(request.data.get('new_type')).lower()
        max_length = request.data.get('max_length')
        requirement = self._text(request.data.get('requirement')).lower()
        has_default_value = 'default_value' in request.data
        default_value = request.data.get('default_value')
        has_conditional_parameter = 'conditional_parameter' in request.data
        conditional_parameter, conditional_error = _conditional_parameter_value(
            request.data.get('conditional_parameter'),
            field_name,
        )

        if not field_name:
            return Response({'error': '"field" is required.'}, status=status.HTTP_400_BAD_REQUEST)

        field = _model_field_for_column(model, field_name)
        db_column = field.db_column or field.column if field else field_name
        if field and (field.primary_key or field.is_relation):
            return Response({'error': 'Primary keys and relationships cannot be modified.'}, status=status.HTTP_400_BAD_REQUEST)

        info = _column_info(db_table, db_column)
        if not info:
            return Response(
                {'error': f'Column "{field_name}" not found in database.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if requirement and requirement not in {'mandatory', 'optional'}:
            return Response({'error': 'Requirement must be mandatory or optional.'}, status=status.HTTP_400_BAD_REQUEST)
        if conditional_error:
            return Response({'error': conditional_error}, status=status.HTTP_400_BAD_REQUEST)

        if not new_type and max_length in (None, '') and not has_default_value and not requirement and not has_conditional_parameter:
            return Response(
                {'error': 'Send new_type, max_length, requirement, default_value, or conditional_parameter to update.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        has_column_change = bool(
            new_type or max_length not in (None, '') or has_default_value or requirement
        )
        existing_conditional_parameter = SchemaColumnMetadata.objects.filter(
            table_name=db_table,
            column_name=db_column,
        ).values_list('conditional_parameter', flat=True).first() or ''

        sql_type, type_error = self._update_sql_type(info, new_type)
        if type_error:
            return Response({'error': type_error}, status=status.HTTP_400_BAD_REQUEST)

        if max_length not in (None, ''):
            try:
                max_length = int(max_length)
            except (TypeError, ValueError):
                return Response({'error': 'max_length must be a number.'}, status=status.HTTP_400_BAD_REQUEST)

            if max_length < 1 or max_length > 65535:
                return Response({'error': 'max_length must be between 1 and 65535.'}, status=status.HTTP_400_BAD_REQUEST)
            if new_type and new_type != 'str':
                return Response({'error': 'max_length can only be changed for VARCHAR/str columns.'}, status=status.HTTP_400_BAD_REQUEST)
            if info['data_type'].lower() != 'varchar' and not new_type:
                return Response({'error': 'max_length can only be changed for VARCHAR/str columns.'}, status=status.HTTP_400_BAD_REQUEST)
            sql_type = f'VARCHAR({max_length})'

        old_field = _existing_schema_field(model, field_name, db_column, info)
        new_db_default = (
            default_value if has_default_value and default_value is not None
            else info['default'] if not has_default_value and info['default'] is not None
            else models.NOT_PROVIDED
        )
        temporary_default = (
            _empty_value_for_sql_type(sql_type)
            if requirement == 'mandatory' and new_db_default is models.NOT_PROVIDED
            else models.NOT_PROVIDED
        )
        new_field = _schema_field_for_sql_type(
            model,
            old_field.name,
            sql_type,
            null=(
                requirement == 'optional'
                if requirement
                else info['nullable']
            ),
            default=temporary_default,
            db_default=new_db_default,
            template=old_field,
        )

        try:
            # A conditional-parameter-only update must not rebuild the DB
            # column. Rebuilding it can make MySQL revalidate legacy values.
            if has_column_change:
                with connection.schema_editor() as schema_editor:
                    schema_editor.alter_field(model, old_field, new_field)

            if has_conditional_parameter:
                _save_schema_column_metadata(db_table, db_column, conditional_parameter)
                existing_conditional_parameter = conditional_parameter

            updated_info = _column_info(db_table, db_column)
            actual_label = MYSQL_TO_LABEL.get(
                updated_info['data_type'].lower(),
                updated_info['data_type'],
            )
            display_label = _schema_display_label(model, db_column, actual_label)
            updated_field = {
                'name': field_name,
                'db_type': LABEL_TO_DB_TYPE.get(display_label, updated_info['data_type']),
                'label': display_label,
                'max_length': _schema_display_max_length(
                    model,
                    db_column,
                    actual_label,
                    updated_info['max_length'],
                ),
                'nullable': updated_info['nullable'],
                'requirement': _field_requirement(model, field_name, updated_info['nullable']),
                'default': updated_info['default'],
                'conditional_parameter': existing_conditional_parameter,
                'value_max_length': None,
            }
            if model is NseStateCodeMaster and field_name == 'state_name' and updated_info['data_type'] == 'text':
                updated_field['value_max_length'] = updated_field['max_length']
                updated_field['max_length'] = 65535

            logger.info(
                'Schema column updated: table=%s field=%s user_id=%s',
                db_table,
                field_name,
                request.user.id,
            )
            return Response({
                'success': True,
                'table': db_table,
                'field': field_name,
                'updated_field': updated_field,
                'new_type': new_type,
                'sql_type': sql_type,
                'max_length': updated_field['max_length'],
                'requirement': requirement or ('optional' if info['nullable'] else 'mandatory'),
                'conditional_parameter': existing_conditional_parameter,
                'default': default_value if has_default_value else info['default'],
            })
        except Exception:
            logger.exception(
                'Failed to update schema column: table=%s field=%s user_id=%s',
                db_table,
                field_name,
                request.user.id,
            )
            return Response(
                {'error': 'Schema change failed. Check the column definition and server logs.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @staticmethod
    def _update_sql_type(info, new_type):
        if new_type:
            sql_type = FIELD_TYPE_MAP.get(new_type)
            if not sql_type:
                return None, f'Unknown type "{new_type}". Valid types: {list(FIELD_TYPE_MAP)}'

            if new_type == 'str':
                existing_length = info.get('max_length') or 255
                sql_type = f'VARCHAR({existing_length})'
            return sql_type, None

        data_type = info['data_type'].lower()
        if data_type == 'varchar':
            return f'VARCHAR({info["max_length"] or 255})', None
        if data_type in ('text', 'longtext', 'mediumtext'):
            return data_type.upper(), None
        return FIELD_TYPE_MAP.get(MYSQL_TO_LABEL.get(data_type), data_type.upper()), None


schema_view = SchemaView.as_view()

ROW_EDITABLE_TABLES = {
    BseStarMfDependencyMaster: {
        'name_field': 'dependency',
        'code_field': 'dependency_code',
        'name_label': 'Dependency',
        'code_label': 'Dependency code',
        'not_found': 'Dependency not found.',
        'log_name': 'BSE Star MF dependency',
    },
    BseStarMfGenderMaster: {
        'name_field': 'gender',
        'code_field': 'gender_code',
        'name_label': 'Gender',
        'code_label': 'Gender code',
        'not_found': 'Gender not found.',
        'log_name': 'BSE Star MF gender',
    },
    BseStarMfStateCodeMaster: {
        'name_field': 'state_name',
        'code_field': 'state_code',
        'name_label': 'State name',
        'code_label': 'State code',
        'not_found': 'State code not found.',
        'log_name': 'BSE Star MF state code',
    },
    BseStarMfTaxStatusMaster: {
        'name_field': 'tax_status',
        'code_field': 'tax_code',
        'name_label': 'Tax status',
        'code_label': 'Tax code',
        'not_found': 'Tax status not found.',
        'log_name': 'BSE Star MF tax status',
    },
    CkycStateCodeMaster: {
        'name_field': 'state_name',
        'code_field': 'state_code',
        'name_label': 'State name',
        'code_label': 'State code',
        'not_found': 'CKYC state code not found.',
        'log_name': 'CKYC state code',
    },
    KraStatusMaster: {
        'name_field': 'app_status',
        'code_field': 'kra_code',
        'extra_fields': ('update_flag',),
        'name_label': 'APP status',
        'code_label': 'KRA code',
        'not_found': 'KRA status mapping not found.',
        'log_name': 'KRA status mapping',
    },
    KraMaritalStatusMaster: {
        'name_field': 'marital_status',
        'code_field': 'marital_code',
        'name_label': 'Marital status',
        'code_label': 'Marital code',
        'not_found': 'KRA marital status not found.',
        'log_name': 'KRA marital status',
    },
    KraGenderMaster: {
        'name_field': 'gender',
        'code_field': 'gender_code',
        'name_label': 'Gender',
        'code_label': 'Gender code',
        'not_found': 'KRA gender not found.',
        'log_name': 'KRA gender',
    },
    KraErrorCode: {
        'name_field': 'code',
        'code_field': 'message',
        'name_label': 'Error code',
        'code_label': 'Error message',
        'not_found': 'KRA error code not found.',
        'log_name': 'KRA error code',
    },
    NseStateCodeMaster: {
        'name_field': 'state_name',
        'code_field': 'state_code',
        'name_label': 'State name',
        'code_label': 'State code',
        'not_found': 'State code not found.',
        'log_name': 'NSE state code',
    },
    NseIncomeRangeMaster: {
        'name_field': 'income_range',
        'code_field': 'income_code',
        'name_label': 'Income range',
        'code_label': 'Income code',
        'not_found': 'Income range not found.',
        'log_name': 'NSE income range',
    },
    NseMaritalStatusMaster: {
        'name_field': 'marital_status',
        'code_field': 'marital_code',
        'name_label': 'Marital status',
        'code_label': 'Marital code',
        'not_found': 'Marital status not found.',
        'log_name': 'NSE marital status',
    },
    NseOccupationMaster: {
        'name_field': 'occupation_name',
        'code_field': 'occupation_code',
        'name_label': 'Occupation name',
        'code_label': 'Occupation code',
        'not_found': 'Occupation code not found.',
        'log_name': 'NSE occupation',
    },
    BseIncomeRangeMaster: {
        'name_field': 'income_range',
        'code_field': 'income_code',
        'name_label': 'Income range',
        'code_label': 'Income code',
        'not_found': 'Income range not found.',
        'log_name': 'BSE income range',
    },
    NsdlStateCodeMaster: {
        'name_field': 'state_name',
        'code_field': 'state_code',
        'name_label': 'State name',
        'code_label': 'State code',
        'not_found': 'State code not found.',
        'log_name': 'NSDL state code',
    },
    NsdlIncomeRangeMaster: {
        'name_field': 'income_range',
        'code_field': 'income_code',
        'name_label': 'Income range',
        'code_label': 'Income code',
        'not_found': 'Income range not found.',
        'log_name': 'NSDL income range',
    },
    NsdlOccupationMaster: {
        'name_field': 'occupation_name',
        'code_field': 'occupation_code',
        'name_label': 'Occupation name',
        'code_label': 'Occupation code',
        'not_found': 'Occupation code not found.',
        'log_name': 'NSDL occupation',
    },
    NsdlRelationMaster: {
        'name_field': 'relation_name',
        'code_field': 'relation_code',
        'name_label': 'Relation name',
        'code_label': 'Relation code',
        'not_found': 'Relation code not found.',
        'log_name': 'NSDL relation',
    },
    NsdlAccountTypeMaster: {
        'name_field': 'account_type',
        'code_field': 'account_code',
        'name_label': 'Account type',
        'code_label': 'Account code',
        'not_found': 'Account type code not found.',
        'log_name': 'NSDL account type',
    },
    NsdlGenderMaster: {
        'name_field': 'gender',
        'code_field': 'gender_code',
        'name_label': 'Gender',
        'code_label': 'Gender code',
        'not_found': 'Gender code not found.',
        'log_name': 'NSDL gender',
    },
    NsdlCountryMaster: {
        'name_field': 'country',
        'code_field': 'country_code',
        'name_label': 'Country',
        'code_label': 'Country code',
        'not_found': 'Country code not found.',
        'log_name': 'NSDL country',
    },
    McxStateCityMaster: {
        'name_field': 'city',
        'code_field': 'state_city_code',
        'extra_fields': ('state',),
        'name_label': 'City',
        'code_label': 'State-city code',
        'not_found': 'MCX state-city mapping not found.',
        'log_name': 'MCX state-city mapping',
    },
    McxErrorCode: {
        'name_field': 'code',
        'code_field': 'message',
        'name_label': 'Error code',
        'code_label': 'Error message',
        'not_found': 'MCX error code not found.',
        'log_name': 'MCX error code',
    },
    McxMaritalStatusMaster: {
        'name_field': 'marital_status',
        'code_field': 'marital_code',
        'name_label': 'Marital status',
        'code_label': 'Marital code',
        'not_found': 'MCX marital status not found.',
        'log_name': 'MCX marital status',
    },
    McxGenderMaster: {
        'name_field': 'gender',
        'code_field': 'gender_code',
        'name_label': 'Gender',
        'code_label': 'Gender code',
        'not_found': 'MCX gender not found.',
        'log_name': 'MCX gender',
    },
    McxIncomeRangeMaster: {
        'name_field': 'income_range',
        'code_field': 'income_code',
        'name_label': 'Income range',
        'code_label': 'Income code',
        'not_found': 'MCX income range not found.',
        'log_name': 'MCX income range',
    },
    McxOccupationMaster: {
        'name_field': 'occupation_name',
        'code_field': 'occupation_code',
        'name_label': 'Occupation name',
        'code_label': 'Occupation code',
        'not_found': 'MCX occupation not found.',
        'log_name': 'MCX occupation',
    },
    McxAccountTypeMaster: {
        'name_field': 'account_type',
        'code_field': 'account_code',
        'name_label': 'Account type',
        'code_label': 'Account code',
        'not_found': 'MCX account type not found.',
        'log_name': 'MCX account type',
    },
    MseStateCodeMaster: {
        'name_field': 'state_name',
        'code_field': 'state_code',
        'name_label': 'State name',
        'code_label': 'State code',
        'not_found': 'MSE state code not found.',
        'log_name': 'MSE state code',
    },
    MseIncomeRangeMaster: {
        'name_field': 'income_range',
        'code_field': 'income_code',
        'name_label': 'Income range',
        'code_label': 'Income code',
        'not_found': 'MSE income range not found.',
        'log_name': 'MSE income range',
    },
    MseOccupationMaster: {
        'name_field': 'occupation_name',
        'code_field': 'occupation_code',
        'name_label': 'Occupation name',
        'code_label': 'Occupation code',
        'not_found': 'MSE occupation not found.',
        'log_name': 'MSE occupation',
    },
    MseAccountTypeMaster: {
        'name_field': 'account_type',
        'code_field': 'account_code',
        'name_label': 'Account type',
        'code_label': 'Account code',
        'not_found': 'MSE account type not found.',
        'log_name': 'MSE account type',
    },
}


ROW_EDITABLE_TABLES[CdslStateCodeMaster] = {**ROW_EDITABLE_TABLES[NseStateCodeMaster], 'log_name': 'CDSL state code'}
ROW_EDITABLE_TABLES[CdslIncomeRangeMaster] = {**ROW_EDITABLE_TABLES[NseIncomeRangeMaster], 'log_name': 'CDSL income range'}


@api_view(['GET', 'POST', 'PATCH', 'DELETE'])
def table_data_view(request, table_name):
    """
    GET /api/table/<name>/data/?page=1&page_size=10&search=...
    Data browser query that avoids ORM field converters for legacy column data.
    """
    model = TABLE_MAP.get(table_name.lower())
    if not model:
        return Response({'error': f'Table "{table_name}" not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method != 'GET':
        if model in (Nse, Bse, BseStarMf, Cdsl, Ckyc, Kra, Nsdl, Mcx, Mse):
            if not (request.user.is_staff or request.user.is_superuser):
                return Response({'error': 'Permission denied.'}, status=403)
            if request.method not in ('POST', 'PATCH'):
                return Response({'error': 'Only record creation and updates are supported.'}, status=405)
            field_name = request.data.get('field', '')
            row_id = request.data.get('id')
            if 'value' not in request.data:
                return Response({'error': 'Column value is required.'}, status=400)
            field = next((f for f in model._meta.fields if f.column == field_name), None)
            if not field or field.primary_key or field.is_relation or (request.method == 'PATCH' and row_id is None):
                return Response({'error': 'Select a record and an editable column.'}, status=400)
            value = request.data.get('value')
            info = _column_info(model._meta.db_table, field.column)
            if not info or (value is None and not info['nullable']):
                return Response({'error': 'This column cannot be empty (NULL).'}, status=400)
            if value is not None and not isinstance(value, str):
                return Response({'error': 'Column value must be text or NULL.'}, status=400)
            configured_length = (
                KRA_COLUMN_MAX_LENGTHS.get(field.column, info['max_length'])
                if model is Kra else info['max_length']
            )
            if isinstance(value, str) and configured_length and len(value) > configured_length:
                return Response({'error': 'Value exceeds the column length.'}, status=400)
            quote = connection.ops.quote_name
            try:
                if request.method == 'POST':
                    row = model.objects.create(**{field.name: value})
                    row_id = row.pk
                with connection.cursor() as cur:
                    if request.method == 'PATCH':
                        cur.execute(f'SELECT {quote(model._meta.pk.column)} FROM {quote(model._meta.db_table)} WHERE {quote(model._meta.pk.column)} = %s', [row_id])
                        if cur.fetchone() is None:
                            return Response({'error': 'Record not found.'}, status=404)
                        cur.execute(f'UPDATE {quote(model._meta.db_table)} SET {quote(field.column)} = %s WHERE {quote(model._meta.pk.column)} = %s', [value, row_id])
                    # Return persisted values, including database type conversions,
                    # so the frontend can update this record without another GET.
                    cur.execute(f'SELECT * FROM {quote(model._meta.db_table)} WHERE {quote(model._meta.pk.column)} = %s', [row_id])
                    saved_row = {column[0]: str(item) if item is not None else ''
                                 for column, item in zip(cur.description, cur.fetchone())}
                return Response({'success': True, 'id': row_id, 'row': saved_row},
                                status=201 if request.method == 'POST' else 200)
            except Exception:
                logger.exception('Could not update record in %s', model._meta.db_table)
                return Response({'error': 'Could not save value. Check its type and uniqueness.'}, status=400)
        if model not in ROW_EDITABLE_TABLES:
            return Response({'error': 'This table does not support row editing.'}, status=status.HTTP_400_BAD_REQUEST)
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        config = ROW_EDITABLE_TABLES[model]
        name_field = config['name_field']
        code_field = config['code_field']
        extra_fields = tuple(config.get('extra_fields', ()))
        name_label = config['name_label']
        code_label = config['code_label']

        if request.method == 'POST':
            name_value = request.data.get(name_field, '').strip()
            code_value = request.data.get(code_field, '').strip()
            extra_values = {
                field_name: request.data.get(field_name, '').strip()
                for field_name in extra_fields
            }
            if not name_value or not code_value or any(not value for value in extra_values.values()):
                return Response({'error': f'{name_label} and {code_label} are required.'}, status=status.HTTP_400_BAD_REQUEST)

            lookup = {f'{name_field}__iexact': name_value}
            lookup.update({f'{field_name}__iexact': value for field_name, value in extra_values.items()})
            row = model.objects.filter(**lookup).first()
            created = row is None
            if row is None:
                row = model()
            setattr(row, name_field, name_value)
            setattr(row, code_field, code_value)
            if model is KraErrorCode:
                row.message_limit = len(code_value)
            for field_name, value in extra_values.items():
                setattr(row, field_name, value)
            row.save()
            logger.info("%s %s: id=%s user_id=%s", config['log_name'], "created" if created else "updated", row.id, request.user.id)
            return Response(
                {'success': True, 'row': _model_row_payload(row)},
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        row_id = request.data.get('id') or request.GET.get('id')
        if not row_id:
            return Response({'error': 'id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            row = model.objects.get(id=row_id)
        except (model.DoesNotExist, ValueError, TypeError, OverflowError):
            return Response({'error': config['not_found']}, status=status.HTTP_404_NOT_FOUND)

        if request.method == 'DELETE':
            row.delete()
            logger.info("%s deleted: id=%s user_id=%s", config['log_name'], row_id, request.user.id)
            return Response({'success': True})

        name_value = request.data.get(name_field, getattr(row, name_field)).strip()
        code_value = request.data.get(code_field, getattr(row, code_field)).strip()
        extra_values = {
            field_name: request.data.get(field_name, getattr(row, field_name)).strip()
            for field_name in extra_fields
        }
        if not name_value or not code_value or any(not value for value in extra_values.values()):
            return Response({'error': f'{name_label} and {code_label} are required.'}, status=status.HTTP_400_BAD_REQUEST)

        setattr(row, name_field, name_value)
        setattr(row, code_field, code_value)
        if model is KraErrorCode:
            row.message_limit = len(code_value)
        for field_name, value in extra_values.items():
            setattr(row, field_name, value)
        row.save()
        logger.info("%s updated: id=%s user_id=%s", config['log_name'], row.id, request.user.id)
        return Response({'success': True, 'row': _model_row_payload(row)})

    if model is not UserDetails and not (request.user.is_staff or request.user.is_superuser):
        return Response({'error': 'Permission denied.'}, status=403)

    search = request.GET.get('search', '').strip()[:200]
    company_user = _requested_company_user(request) if model is UserDetails else None
    if model is UserDetails and company_user is None:
        return Response({'error': 'Company not found.'}, status=status.HTTP_404_NOT_FOUND)
    try:
        page = max(1, int(request.GET.get('page', 1)))
        page_size = min(100, max(1, int(request.GET.get('page_size', 10))))
    except ValueError:
        page = 1
        page_size = 10

    model_database_columns = _model_database_columns(model, model._meta.db_table)
    fields = [
        field
        for field in model._meta.get_fields()
        if field.concrete and field.column in model_database_columns
    ]
    pk_name = model._meta.pk.name
    ordered_fields = sorted(fields, key=lambda f: 0 if f.name == pk_name else 1)
    columns = [f.name for f in ordered_fields]
    db_columns = {f.name: f.db_column or f.column for f in ordered_fields}

    requested_columns = request.GET.get('columns', '')
    selected_db_columns = {column: column for column in columns}
    if requested_columns:
        selected = list(dict.fromkeys(requested_columns.split(',')))
        aliases = TABLE_COLUMN_ALIASES.get(model, {})
        resolved = [aliases.get(column, column) for column in selected]
        if any(column not in db_columns for column in resolved):
            return Response({'error': 'Unknown requested column.'}, status=400)
        columns = selected
        selected_db_columns = dict(zip(selected, resolved))

    quote_name = connection.ops.quote_name
    db_table = quote_name(model._meta.db_table)
    select_cols = ', '.join(
        f'{quote_name(db_columns[selected_db_columns[col]])} AS {quote_name(col)}'
        for col in columns
    )

    searchable_fields = {
        'clientcode', 'name', 'aadhaar_name', 'email', 'pan', 'panno', 'clientname', 'mobile',
        'mobilenumber', 'state_name', 'state_code', 'income_range', 'income_code',
        'state', 'city', 'state_city_code', 'code', 'message', 'app_status', 'update_flag',
        'kra_code', 'marital_status', 'marital_code', 'gender', 'gender_code',
        'occupation_name', 'occupation_code', 'account_type', 'account_code',
    }
    searchable_cols = [col for col in db_columns if col.lower() in searchable_fields]
    where_sql = ''
    params = []
    fixed_where = []
    if model is UserDetails:
        fixed_where.append(f'{quote_name(db_columns["user"])} = %s')
        params.append(company_user.id)

    if search and searchable_cols:
        where_parts = [f'{quote_name(db_columns[col])} LIKE %s' for col in searchable_cols]
        fixed_where.append(f"({' OR '.join(where_parts)})")
        params.extend([f'%{search}%'] * len(searchable_cols))

    if fixed_where:
        where_sql = f" WHERE {' AND '.join(fixed_where)}"

    with connection.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM {db_table}{where_sql}', params)
        total = cur.fetchone()[0]

        total_pages = max(1, (total + page_size - 1) // page_size)
        page = min(page, total_pages)
        offset = (page - 1) * page_size

        cur.execute(
            f'SELECT {select_cols} FROM {db_table}{where_sql} ORDER BY {quote_name(db_columns[pk_name])} LIMIT %s OFFSET %s',
            [*params, page_size, offset],
        )
        result_columns = [col[0] for col in cur.description]
        formatted_rows = [
            {
                col: str(val) if val is not None else ''
                for col, val in zip(result_columns, row)
            }
            for row in cur.fetchall()
        ]

    if model is UserDetails and 'clientcode' in columns and formatted_rows:
        clientcodes = [row.get('clientcode', '') for row in formatted_rows if row.get('clientcode')]
        try:
            uploads = (
                CdslUpload.objects
                .select_related('client')
                .filter(
                    client__user=company_user,
                    client__clientcode__in=clientcodes,
                )
                .order_by('-id')
            )
            latest_uploads = {}
            for upload in uploads:
                latest_uploads.setdefault(upload.client.clientcode, upload)

            for row in formatted_rows:
                upload = latest_uploads.get(row.get('clientcode'))
                row.update({
                    'cdsl_upload_id': str(upload.id) if upload else '',
                    'cdsl_upload_timestamp': (
                        localtime(upload.created_at).strftime('%Y-%m-%d %H:%M:%S')
                        if upload and upload.created_at else ''
                    ),
                    'cdsl_upload_status': upload.status if upload else '',
                })
        except DatabaseError:
            logger.exception('Could not load CDSL upload metadata for dashboard')

    return Response({
        'table': table_name,
        'total': total,
        'page': page,
        'total_pages': total_pages,
        'columns': columns,
        'rows': formatted_rows,
    })
