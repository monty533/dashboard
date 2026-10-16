from django.db import migrations


MISSING_KRA_WEB_ERROR_MESSAGES = {
    'WEBERR-029': 'Invalid IP address',
    'WEBERR-030': 'At least one of pdf_Base64 or xml_Base64 or image_Base64 or zip_Base64 must be provided.',
    'WEBERR-031': 'If base64 is provided, filename with proper extension must also be provided.',
    'WEBERR-032': 'please provide the password.',
    'WEBERR-033': 'File is too large. Maximum size is 10 MB.',
    'WEBERR-034': 'File extension does not match the Base64 decoded data or BASE64./ Invalid  file format.',
    'WEBERR-035': 'PAN IS EITHER NOT CREATED OR MODIFIED/PAN IS NOT IN VALID STATUS',
    'WEBERR-040': 'IMAGE SHARING IS NOT ELIGIBLE FOR THIS PAN',
    'WEBERR-042': 'INVALID REFERENCE NUMBER / REFERENCE NUMBER ALREADY CONSUMED',
    'WEBERR-043': 'Initialization Vector (IV) is missing in the request.',
    'WEBERR-044': 'Encrypted request data not provided within double quotes.',
    'WEBERR-045': 'All fields are mandatory. Please provide valid inputs.',
    'WEBERR-046': 'The PDF file is corrupted or incomplete.',
    'WEBERR-047': 'The XML file is corrupted or incomplete.',
    'WEBERR-048': 'The ZIP file is corrupted or incomplete.',
    'WEBERR-049': 'The IMG file is corrupted or incomplete.',
    'WEBERR-050': 'The PDF file size exceeds the allowed limit of 10 MB.',
    'WEBERR-051': 'The XML file size exceeds the allowed limit of 10 MB.',
    'WEBERR-052': 'The ZIP file size exceeds the allowed limit of 10 MB.',
    'WEBERR-053': 'The IMG file size exceeds the allowed limit of 10 MB.',
    'WEBERR-054': 'The PDF file extension does not match the Base64-decoded data.',
    'WEBERR-055': 'The XML file extension does not match the Base64-decoded data.',
    'WEBERR-056': 'The ZIP file extension does not match the Base64-decoded data.',
    'WEBERR-057': 'The IMG file extension does not match the Base64-decoded data.',
    'WEBERR-058': 'If PDF base64 is provided, filename with proper extension must also be provided.',
    'WEBERR-059': 'If XML base64 is provided, filename with proper extension must also be provided.',
    'WEBERR-060': 'If ZIP base64 is provided, filename with proper extension must also be provided.',
    'WEBERR-061': 'If IMG base64 is provided, filename with proper extension must also be provided.',
    'WEBERR-062': 'KYC ID IS MANDATORY.',
    'WEBERR-999': 'Invalid PAN No Format',
}


def add_missing_kra_web_error_codes(apps, schema_editor):
    KraErrorCode = apps.get_model('db_structure', 'KraErrorCode')
    existing_codes = set(
        KraErrorCode.objects.filter(code__in=MISSING_KRA_WEB_ERROR_MESSAGES)
        .values_list('code', flat=True)
    )
    KraErrorCode.objects.bulk_create(
        [
            KraErrorCode(code=code, message=message)
            for code, message in MISSING_KRA_WEB_ERROR_MESSAGES.items()
            if code not in existing_codes
        ],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0119_userdetails_nominee_percentage'),
    ]

    operations = [
        migrations.RunPython(
            add_missing_kra_web_error_codes,
            migrations.RunPython.noop,
        ),
    ]
