from collections.abc import Mapping

from rest_framework import serializers

from .models import USERDETAILS_MANDATORY_COLUMNS, UserDetails


USER_DETAILS_READ_ONLY_FIELDS = frozenset({
    'id',
    'created_at',
    'updated_at',
})

USER_DETAILS_FIELDS = tuple(
    field.name
    for field in UserDetails._meta.concrete_fields
    if field.name != 'user'
)

USER_DETAILS_CONDITIONAL_OPTIONS = {
    'account_holder_type': ('individual', 'jointholder'),
    'modeoftrading': ('offline', 'online'),
    'mode_of_account': ('N', 'M'),
    'transaction_type': ('account_opening', 'segment_addition', 'modification'),
    'activestatus': ('A', 'I'),
    'bse_push': (True, False),
    'bsestarmf_push': (True, False),
    'nse_push': (True, False),
    'nsdl_push': (True, False),
    'cdsl_push': (True, False),
    'mcx_push': (True, False),
    'mse_push': (True, False),
    'ckyc_push': (True, False),
    'kra_push': (True, False),
    'bse_cash_push': (True, False),
    'bse_currency_push': (True, False),
    'bse_fo_push': (True, False),
    'bse_slbm_push': (True, False),
    'bse_cash': ('true', 'false'),
    'bse_currency': ('true', 'false'),
    'bse_fo': ('true', 'false'),
    'bse_slbm': ('true', 'false'),
    'mcx': ('true', 'false'),
    'nse_cash': ('true', 'false'),
    'nse_currency': ('true', 'false'),
    'nse_fo': ('true', 'false'),
    'nse_slbm': ('true', 'false'),
    'nse_cash_push': (True, False),
    'nse_currency_push': (True, False),
    'nse_fo_push': (True, False),
    'nse_slbm_push': (True, False),
    'nominee_check': ('yes', 'no'),
}


class UserDetailsSerializer(serializers.ModelSerializer):
    """Validate and serialize the client-owned UserDetails payload."""

    email = serializers.EmailField(max_length=50)

    class Meta:
        model = UserDetails
        fields = USER_DETAILS_FIELDS
        read_only_fields = tuple(USER_DETAILS_READ_ONLY_FIELDS)
        extra_kwargs = {
            field.name: {
                'required': field.column in USERDETAILS_MANDATORY_COLUMNS,
            }
            for field in UserDetails._meta.concrete_fields
            if field.name not in USER_DETAILS_READ_ONLY_FIELDS and field.name != 'user'
        }

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({
                'body': ['Request body must be a JSON object.'],
            })

        field_names = set(self.fields)
        incoming_fields = set(data)
        unknown_fields = sorted(incoming_fields - field_names)
        read_only_fields = sorted(
            incoming_fields & set(self.Meta.read_only_fields)
        )
        errors = {}
        if unknown_fields:
            errors['unknown_fields'] = [
                f'Unknown field: {field_name}.'
                for field_name in unknown_fields
            ]
        for field_name in read_only_fields:
            errors[field_name] = ['This field is read-only.']
        if errors:
            raise serializers.ValidationError(errors)

        return super().to_internal_value(data)

    def validate(self, attrs):
        errors = {}
        for field_name, options in USER_DETAILS_CONDITIONAL_OPTIONS.items():
            value = attrs.get(field_name)
            if value not in (None, '') and value not in options:
                errors[field_name] = [
                    f'Invalid value. Expected one of: {", ".join(options)}.'
                ]

        if errors:
            raise serializers.ValidationError(errors)
        return attrs
