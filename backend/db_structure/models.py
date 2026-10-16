from django.conf import settings
from django.db import models

from .mcx_constants import ERROR_CODE_MAP


MCX_ERROR_MESSAGE_MAX_LENGTH = max(
    (len(str(message)) for message in ERROR_CODE_MAP.values()),
    default=255,
)

class UserProfile(models.Model):
    """Application-specific fields for Django's built-in auth user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        db_column='user_id',
    )
    company_name = models.CharField(max_length=100, blank=True, default='')
    phone = models.CharField(max_length=10, blank=True, default='')
    address = models.CharField(max_length=150, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profiles'

    def __str__(self):
        return f'Profile for {self.user.username}'


class ClientApiKey(models.Model):
    """Hashed API credentials issued to a registered client user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='client_api_keys',
        db_column='user_id',
    )
    prefix = models.CharField(max_length=20, unique=True)
    key_hash = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'client_api_keys'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.user.username} - {self.prefix}'

# USERDETAILS_COLUMN_MAX_LENGTHS = {
#     # Keep ordinary VARCHAR columns compact so the UserDetails row stays
#     # below MySQL's 8 KB inline-row limit when utf8mb4 is used. Long address
#     # and document-reference fields are listed in USERDETAILS_TEXT_COLUMNS.
#     'clientcode': 50,
#     'pan': 10,
#     'fathername': 25,
#     'mothername': 25,
#     'mobile': 10,
#     'email': 50,
#     'account_holder_type': 15,
#     'networth': 10,
#     'modeoftrading': 7,
#     'mode_of_account': 10,
#     'transaction_type': 20,
#     'dpid': 20,
#     'dptype': 10,
#     'education': 20,
#     'bse_cash': 5,
#     'bse_currency': 5,
#     'bse_fo': 5,
#     'bse_slbm': 5,
#     'mcx': 5,
#     'nse_cash': 5,
#     'nse_currency': 5,
#     'nse_fo': 5,
#     'nse_slbm': 5,
#     'networth_date': 10,
#     # Document references may contain longer relative paths or URLs.
#     'annual_income': 15,
#     'occupation': 20,
#     'marital_status': 10,
#     'bankname': 20,
#     'ifsc': 11,
#     'micr': 9,
#     'branchname': 20,
#     'bank_pincode': 10,
#     'bankaccountnumber': 20,
#     'accounttype': 15,
#     'activestatus': 1,
#     'aadhaar_name': 25,
#     'aadhaar_dob': 10,
#     'aadhaar_gender': 10,
#     'aadhaar_pincode': 10,
#     'aadhaar_no': 12,
#     'isdppoa': 5,
#     'annual_income_date': 10,
#     'nominee_check': 3,
#     'bsda_flag': 10,
#     'pledge_standing_instruction': 5,
#     'mse_status': 20,
#     'mse_request_no': 50,
#     'kra_sftp_response': 255,
# }

# for number in (1, 2, 3):
#     USERDETAILS_COLUMN_MAX_LENGTHS.update({
#         f'nominee{number}_firstname': 25,
#         f'nominee{number}_middlename': 25,
#         f'nominee{number}_lastname': 25,
#         f'nominee{number}_pan': 10,
#         f'nominee{number}_dob': 10,
#         f'nominee{number}_relation': 20,
#         f'nominee{number}_pincode': 6,
#         f'nominee{number}_mobile': 10,
#         f'nominee{number}_email': 50,
#         f'nominee{number}_percentage': 6,
#     })

# # Keep address values and document URL/reference values as TEXT because they
# # can be longer than normal VARCHAR fields. All other UserDetails string
# # fields remain VARCHAR through _userdetailstr().
# USERDETAILS_TEXT_COLUMNS = {
#     'addressline1', 'addressline2', 'addressline3',
#     'uploadpan', 'uploadsignature', 'pdf_file_kra', 'aadhar_xml',
#     'aadhaar_house', 'aadhaar_image', 'aadhaar_file', 'aadhaar_address',
#     'bankaddress', 'bank_city', 'bank_state',
#     'aadhaar_dist', 'aadhaar_state', 'aadhaar_country',
#     *{
#         f'nominee{number}_{suffix}'
#         for number in (1, 2, 3)
#         for suffix in (
#             'address1', 'address2', 'city', 'state', 'country',
#         )
#     },
# }

# USERDETAILS_MANDATORY_COLUMNS = {
#     'clientcode',
#     'aadhaar_name',
#     'pan',
#     'fathername',
#     'mothername',
#     'mobile',
#     'email',
#     'account_holder_type',
#     'addressline1',
#     'addressline2',
#     'addressline3',
#     'networth',
#     'modeoftrading',
#     'mode_of_account',
#     'transaction_type',
#     'dpid',
#     'dptype',
#     'education',
#     'bse_cash',
#     'bse_currency',
#     'bse_fo',
#     'bse_slbm',
#     'mcx',
#     'nse_cash',
#     'nse_currency', 
#     'nse_fo',
#     'nse_slbm',
#     'networth_date',
#     'uploadpan',
#     'uploadsignature',
#     'annual_income',
#     'occupation',
#     'aadhaar_address',
#     'marital_status',
#     'bankname',
#     'ifsc',
#     'micr',
#     'branchname',
#     'bankaddress',
#     'bankaccountnumber',
#     'accounttype',
#     'activestatus',
#     'aadhaar_dob',
#     'aadhaar_gender',
#     'aadhaar_house',
#     'aadhaar_dist',
#     'aadhaar_state',
#     'aadhaar_country',
#     'aadhaar_image',
#     'aadhaar_file',
#     'aadhaar_pincode',
#     'aadhaar_no',
#     'isdppoa',
#     'nominee_check',
# }


# def _userdetailstr(col, **kw):
#     db_column = kw.pop('db_column', col)
#     required = col in USERDETAILS_MANDATORY_COLUMNS
#     if required:
#         kw.setdefault('default', '')
#     null = kw.pop('null', not required)
#     blank = kw.pop('blank', not required)
#     # Keep max_length validation in Django.  Only selected long/repeated
#     # values use TEXT to avoid making every UserDetails column a TEXT column.
#     use_text = col in USERDETAILS_TEXT_COLUMNS and not (kw.get('unique') or kw.get('db_index'))
#     field_class = models.TextField if use_text else models.CharField
#     if use_text:
#         # TextField has no VARCHAR length requirement. Do not pass a
#         # max_length value, so document/address text remains unrestricted.
#         kw.pop('max_length', None)
#     else:
#         kw.setdefault('max_length', USERDETAILS_COLUMN_MAX_LENGTHS[col])
#     return field_class(null=null, blank=blank, db_column=db_column, **kw)


# def _userdetailspk(col):
#     return models.BigAutoField(primary_key=True, db_column=col)

# class UserDetails(models.Model):
#     id           = _userdetailspk('id')
#     created_at   = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at   = models.DateTimeField(auto_now=True, db_column='updated_at')
#     # Identity
#     user         = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, db_column='user_id', related_name='userdetails')
#     clientcode   = _userdetailstr('clientcode', unique=True)
#     pan          = _userdetailstr('pan')
#     fathername   = _userdetailstr('fathername')
#     mothername   = _userdetailstr('mothername')
#     mobile       = _userdetailstr('mobile')
#     email        = _userdetailstr('email')
#     account_holder_type         = _userdetailstr('account_holder_type', default='individual')

#     # Address
#     addressline1 = _userdetailstr('addressline1')
#     addressline2 = _userdetailstr('addressline2')
#     addressline3 = _userdetailstr('addressline3')

#     # Trading
#     networth      = _userdetailstr('networth')
#     networth_date = _userdetailstr('networth_date')
#     modeoftrading = _userdetailstr('modeoftrading')
#     mode_of_account = _userdetailstr('mode_of_account')
#     transaction_type = _userdetailstr('transaction_type', default='account_opening')
#     dpid          = _userdetailstr('dpid')
#     dptype        = _userdetailstr('dptype')
#     education     = _userdetailstr('education')

#     # Exchange preferences
#     bse_cash     = _userdetailstr('bse_cash')
#     bse_currency = _userdetailstr('bse_currency')
#     bse_fo       = _userdetailstr('bse_fo')
#     bse_slbm     = _userdetailstr('bse_slbm')
#     mcx          = _userdetailstr('mcx')
#     nse_cash     = _userdetailstr('nse_cash')
#     nse_currency = _userdetailstr('nse_currency')
#     nse_fo       = _userdetailstr('nse_fo')
#     nse_slbm     = _userdetailstr('nse_slbm')


#     # Document uploads
#     uploadpan       = _userdetailstr('uploadpan')
#     uploadsignature = _userdetailstr('uploadsignature')
#     # Optional CVL KRA document references. These are uploaded to the KRA
#     # SFTP folder after the encrypted KRA API request is accepted.
#     pdf_file_kra    = _userdetailstr('pdf_file_kra')
#     aadhar_xml      = _userdetailstr('aadhar_xml')

#     # Profile / KYC
#     annual_income       = _userdetailstr('annual_income')
#     annual_income_date  = _userdetailstr('annual_income_date')
#     occupation          = _userdetailstr('occupation')
#     marital_status      = _userdetailstr('marital_status')

#     # Bank
#     bankname          = _userdetailstr('bankname')
#     ifsc              = _userdetailstr('ifsc')
#     micr              = _userdetailstr('micr')
#     branchname        = _userdetailstr('branchname')
#     bankaddress       = _userdetailstr('bankaddress')
#     bank_city         = _userdetailstr('bank_city')
#     bank_state        = _userdetailstr('bank_state')
#     bank_pincode      = _userdetailstr('bank_pincode')
#     bankaccountnumber = _userdetailstr('bankaccountnumber')
#     accounttype       = _userdetailstr('accounttype')

#     # Status / Workflow
#     activestatus = _userdetailstr('activestatus')

#     # Aadhaar
#     aadhaar_name       = _userdetailstr('aadhaar_name')
#     aadhaar_dob        = _userdetailstr('aadhaar_dob')
#     aadhaar_gender     = _userdetailstr('aadhaar_gender')
#     aadhaar_house      = _userdetailstr('aadhaar_house')
#     aadhaar_dist       = _userdetailstr('aadhaar_dist')
#     aadhaar_state      = _userdetailstr('aadhaar_state')
#     aadhaar_country    = _userdetailstr('aadhaar_country')
#     aadhaar_image      = _userdetailstr('aadhaar_image')
#     aadhaar_file       = _userdetailstr('aadhaar_file')
#     aadhaar_pincode    = _userdetailstr('aadhaar_pincode')
#     aadhaar_address    = _userdetailstr('aadhaar_address')
#     aadhaar_no         = _userdetailstr('aadhaar_no')

#     pledge_standing_instruction  = _userdetailstr('pledge_standing_instruction')
#     bsda_flag         = _userdetailstr('bsda_flag')

#     # Segments
#     isdppoa = _userdetailstr('isdppoa')

#     # Nominee details
#     nominee1_firstname = _userdetailstr('nominee1_firstname')
#     nominee1_middlename = _userdetailstr('nominee1_middlename')
#     nominee1_lastname = _userdetailstr('nominee1_lastname')
#     nominee1_pan = _userdetailstr('nominee1_pan')
#     nominee1_dob = _userdetailstr('nominee1_dob')
#     nominee1_relation = _userdetailstr('nominee1_relation')
#     nominee1_address1 = _userdetailstr('nominee1_address1')
#     nominee1_address2 = _userdetailstr('nominee1_address2')
#     nominee1_city = _userdetailstr('nominee1_city')
#     nominee1_state = _userdetailstr('nominee1_state')
#     nominee1_country = _userdetailstr('nominee1_country')
#     nominee1_pincode = _userdetailstr('nominee1_pincode')
#     nominee1_mobile = _userdetailstr('nominee1_mobile')
#     nominee1_email = _userdetailstr('nominee1_email')
#     nominee1_percentage = _userdetailstr('nominee1_percentage')

#     nominee2_firstname = _userdetailstr('nominee2_firstname')
#     nominee2_middlename = _userdetailstr('nominee2_middlename')
#     nominee2_lastname = _userdetailstr('nominee2_lastname')
#     nominee2_pan = _userdetailstr('nominee2_pan')
#     nominee2_dob = _userdetailstr('nominee2_dob')
#     nominee2_relation = _userdetailstr('nominee2_relation')
#     nominee2_address1 = _userdetailstr('nominee2_address1')
#     nominee2_address2 = _userdetailstr('nominee2_address2')
#     nominee2_city = _userdetailstr('nominee2_city')
#     nominee2_state = _userdetailstr('nominee2_state')
#     nominee2_country = _userdetailstr('nominee2_country')
#     nominee2_pincode = _userdetailstr('nominee2_pincode')
#     nominee2_mobile = _userdetailstr('nominee2_mobile')
#     nominee2_email = _userdetailstr('nominee2_email')
#     nominee2_percentage = _userdetailstr('nominee2_percentage')

#     nominee3_firstname  = _userdetailstr('nominee3_firstname')
#     nominee3_middlename = _userdetailstr('nominee3_middlename')
#     nominee3_lastname   = _userdetailstr('nominee3_lastname')
#     nominee3_pan        = _userdetailstr('nominee3_pan')
#     nominee3_dob        = _userdetailstr('nominee3_dob')
#     nominee3_relation = _userdetailstr('nominee3_relation')
#     nominee3_address1 = _userdetailstr('nominee3_address1')
#     nominee3_address2 = _userdetailstr('nominee3_address2')
#     nominee3_city = _userdetailstr('nominee3_city')
#     nominee3_state = _userdetailstr('nominee3_state')
#     nominee3_country = _userdetailstr('nominee3_country')
#     nominee3_pincode = _userdetailstr('nominee3_pincode')
#     nominee3_mobile = _userdetailstr('nominee3_mobile')
#     nominee3_email = _userdetailstr('nominee3_email')
#     nominee3_percentage = _userdetailstr('nominee3_percentage')
#     nominee_check = _userdetailstr('nominee_check')

#     bse_cash_push = models.BooleanField(null=False, blank=True, default=False, db_column='bse_cash_push')
#     bse_currency_push = models.BooleanField(null=False, blank=True, default=False, db_column='bse_currency_push')
#     bse_fo_push = models.BooleanField(null=False, blank=True, default=False, db_column='bse_fo_push')
#     bse_slbm_push = models.BooleanField(null=False, blank=True, default=False, db_column='bse_slbm_push')
#     nse_cash_push = models.BooleanField(null=False, blank=True, default=False, db_column='nse_cash_push')
#     nse_currency_push = models.BooleanField(null=False, blank=True, default=False, db_column='nse_currency_push')
#     nse_fo_push = models.BooleanField(null=False, blank=True, default=False, db_column='nse_fo_push')
#     nse_slbm_push = models.BooleanField(null=False, blank=True, default=False, db_column='nse_slbm_push')

#     # Client-controlled provider permissions: False=do not push, True=allow push.
#     # The *_push_at fields record the latest successful provider push.
#     cdsl_push = models.BooleanField(null=False, blank=True, default=False, db_column='cdsl_push')
#     cdsl_push_at = models.DateTimeField(null=True, blank=True, db_column='cdsl_push_at')

#     bse_push = models.BooleanField(null=False, blank=True, default=False, db_column='bse_push')
#     bsestarmf_push = models.BooleanField(null=False, blank=True, default=False, db_column='bsestarmf_push')
#     nse_push = models.BooleanField(null=False, blank=True, default=False, db_column='nse_push')
#     nsdl_push = models.BooleanField(null=False, blank=True, default=False, db_column='nsdl_push')
#     mcx_push = models.BooleanField(null=False, blank=True, default=False, db_column='mcx_push')
#     mse_push = models.BooleanField(null=False, blank=True, default=False, db_column='mse_push')
#     ckyc_push = models.BooleanField(null=False, blank=True, default=False, db_column='ckyc_push')
#     kra_push = models.BooleanField(null=False, blank=True, default=False, db_column='kra_push')
#     bse_push_at = models.DateTimeField(null=True, blank=True, db_column='bse_push_at')
#     bsestarmf_push_at = models.DateTimeField(null=True, blank=True,db_column='bsestarmf_push_at')
#     mcx_push_at = models.DateTimeField(null=True, blank=True, db_column='mcx_push_at')
#     nsdl_push_at = models.DateTimeField(null=True, blank=True, db_column='nsdl_push_at')
#     mse_push_at = models.DateTimeField(null=True, blank=True, db_column='mse_push_at')
#     ckyc_push_at = models.DateTimeField(null=True, blank=True, db_column='ckyc_push_at')
#     kra_push_at = models.DateTimeField(null=True, blank=True, db_column='kra_push_at')
#     nse_push_at = models.DateTimeField(null=True, blank=True, db_column='nse_push_at')
#     mse_in_process = models.BooleanField(null=False, blank=True, default=False, db_column='mse_in_process')
#     mse_request_no = _userdetailstr('mse_request_no', null=False, blank=True, default='')
#     mse_status = _userdetailstr('mse_status', null=False, blank=True, default='')
#     kra_sftp_response = _userdetailstr('kra_sftp_response', null=False, blank=True, default='')

#     class Meta:
#         db_table = 'userdetails'

#     def __str__(self):
#         return f"{self.clientcode}"


# BSE_COLUMN_MAX_LENGTHS = {
#     'TRANSACTIONCODE': 50,
#     'CLIENTTYPE': 50,
#     'STATUS': 50,
#     'CATEGORY': 50,
#     'CLIENTCODE': 50,
#     'PANNO': 50,
#     'POLITICALEXPERSON': 50,
#     'ADDRESS1': 50,
#     'PERMNEQUALCORP': 50,
#     'ADDRESS2': 50,
#     'COUNTRY': 50,
#     'STATE': 50,
#     'CITY': 50,
#     'PINCODE': 50,
#     'TYPEOFSERVICE': 50,
#     'CONTACTDETAILS': 50,
#     'EMAIL': 50,
#     'MOBILENUMBER': 50,
#     'STDCODE': 50,
#     'PHONENO': 50,
#     'EQ_CPCODE': 50,
#     'EQCMID': 50,
#     'FNOCPCODE': 50,
#     'FNOCMID': 50,
#     'DEPOSITORYNAME1': 50,
#     'DEMANTID1': 50,
#     'DEPOSITORYPARTICIPANT1': 50,
#     'DEPOSITORYNAME2': 50,
#     'DEMANTID2': 50,
#     'DEPOSITORYPARTICIPANT2': 50,
#     'DEPOSITORYNAME3': 50,
#     'DEMANTID3': 50,
#     'DEPOSITORYPARTICIPANT3': 50,
#     'BANKNAME1': 50,
#     'ACCOUNTNO1': 50,
#     'BANKNAME2': 50,
#     'ACCOUNTNO2': 50,
#     'BANKNAME3': 50,
#     'ACCOUNTNO3': 50,
#     'CLIENTAGGREMENTDATE': 50,
#     'PROVIDEDETAILS': 50,
#     'INCOME': 50,
#     'INCOMEDATE': 50,
#     'NETWORTH': 50,
#     'NETWORTHDATE': 50,
#     'ISACTIVE': 50,
#     'UPDATEREASON': 50,
#     'FIRSTNAME': 50,
#     'MIDDLENAME': 50,
#     'LASTNAME': 50,
#     'AADHARCARDNO': 50,
#     'DATEOFBIRTH': 50,
#     'CLIENTNAME': 50,
#     'REGISTRATIONNO': 50,
#     'REGISTERINGAUTHORITY': 50,
#     'DATEOFREGISTRATION': 50,
#     'PLACEOFREGISTRATION': 50,
#     'WHETHERCORPORATE': 50,
#     'CINNO': 50,
#     'NUMBEROFDIRECTORS': 50,
#     'PARTNERS_KARTAUID': 50,
#     'PARTNERS_COPARCENERUID': 50,
#     'CONTACTPERSONNAME1': 50,
#     'CONTACTPERSONDESIGNATION1': 50,
#     'CONTACTPERSONADDRESS1': 50,
#     'CONTACTPERSONEMAIL1': 50,
#     'CONTACTPERSONPAN1': 50,
#     'CONTACTPERSONMOBILE1': 50,
#     'CONTACTPERSONNAME2': 50,
#     'CONTACTPERSONDESIGNATION2': 50,
#     'CONTACTPERSONADDRESS2': 50,
#     'CONTACTPERSONEMAIL2': 50,
#     'CONTACTPERSONPAN2': 50,
#     'CONTACTPERSONMOBILE2': 50,
#     'SERVERIP': 50,
#     'BATUSER': 50,
#     'CASH': 50,
#     'EQUITY_DERIVATIVE': 50,
#     'SLB': 50,
#     'CURRENCY': 50,
#     'DEBT': 50,
#     'ISPOA': 50,
#     'POAFORFUND': 50,
#     'POAFORSECURITY': 50,
#     'DATEOFPOAFORFUND': 50,
#     'DATEOFPOAFORSECURITY': 50,
#     'PERCOUNTRY': 50,
#     'PERSTATE': 50,
#     'PERCITY': 50,
#     'PERPINCODE': 50,
#     'CURRENCYCPCODE': 50,
#     'CURRENCYCMID': 50,
#     'ENROLLMENTNUMBER': 50,
#     'COMMDERIVATIVES': 50,
#     'OPTEDFORNOMINATION': 50,
#     'CUSTPANNO': 50,
#     'CUSTNAME': 50,
#     'CUSTADDRESS': 50,
#     'CUSTCOUNTRY': 50,
#     'CUSTSTATE': 50,
#     'CUSTCITY': 50,
#     'CUSTPINCODE': 50,
#     'CUSTMOBILENUMBER': 50,
#     'CUSTSTDCODE': 50,
#     'CUSTPHONENO': 50,
#     'CUSTEMAIL': 50,
#     'EGR': 50,
#     'BENEFICIALOWNACNTNO1': 50,
#     'BENEFICIALOWNACNTNO2': 50,
#     'BENEFICIALOWNACNTNO3': 50,
#     'OPTED_FOR_UPI': 50,
#     'BANKBRANCHIFSCCODE1': 50,
#     'PRIMARYORSECONDARYBANK1': 50,
#     'BANKBRANCHIFSCCODE2': 50,
#     'PRIMARYORSECONDARYBANK2': 50,
#     'BANKBRANCHIFSCCODE3': 50,
#     'PRIMARYORSECONDARYBANK3': 50,
#     'BANKBRANCHIFSCCODE4': 50,
#     'BANKNAME4': 50,
#     'ACCOUNTNO4': 50,
#     'PRIMARYORSECONDARYBANK4': 50,
#     'BANKBRANCHIFSCCODE5': 50,
#     'BANKNAME5': 50,
#     'ACCOUNTNO5': 50,
#     'PRIMARYORSECONDARYBANK5': 50,
#     'PRIMARYORSECONDARYDP1': 50,
#     'PRIMARYORSECONDARYDP2': 50,
#     'PRIMARYORSECONDARYDP3': 50,
#     'DEPOSITORYNAME4': 50,
#     'DEMANTID4': 50,
#     'BENEFICIALOWNACNTNO4': 50,
#     'PRIMARYORSECONDARYDP4': 50,
#     'DEPOSITORYNAME5': 50,
#     'DEMANTID5': 50,
#     'BENEFICIALOWNACNTNO5': 50,
#     'PRIMARYORSECONDARYDP5': 50,
#     'CLIENTNAMEDESCRIPTION': 50,
#     'DIRECTORDETAILS': 50,
# }

# BSE_MANDATORY_COLUMNS = {
#     'TRANSACTIONCODE',
#     'CLIENTTYPE',
#     'STATUS',
#     'CATEGORY',
#     'CLIENTCODE',
#     'PANNO',
#     'POLITICALEXPERSON',
#     'ADDRESS1',
#     'PERMNEQUALCORP',
#     'ADDRESS2',
#     'COUNTRY',
#     'STATE',
#     'CITY',
#     'PINCODE',
#     'TYPEOFSERVICE',
#     'CONTACTDETAILS',
#     'EMAIL',
#     'MOBILENUMBER',
#     'DEPOSITORYNAME1',
#     'DEMANTID1',
#     'DEPOSITORYPARTICIPANT1',
#     'BANKNAME1',
#     'ACCOUNTNO1',
#     'BANKNAME2',
#     'ACCOUNTNO2',
#     'BANKNAME3',
#     'ACCOUNTNO3',
#     'PROVIDEDETAILS',
#     'INCOME',
#     'INCOMEDATE',
#     'NETWORTH',
#     'NETWORTHDATE',
#     'ISACTIVE',
#     'FIRSTNAME',
#     'MIDDLENAME',
#     'LASTNAME',
#     'DATEOFBIRTH',
#     'CLIENTNAME',
#     'WHETHERCORPORATE',
#     'NUMBEROFDIRECTORS',
#     'CASH',
#     'EQUITY_DERIVATIVE',
#     'SLB',
#     'CURRENCY',
#     'DEBT',
#     'ISPOA',
#     'POAFORFUND',
#     'POAFORSECURITY',
#     'DATEOFPOAFORFUND',
#     'DATEOFPOAFORSECURITY',
#     'PERCOUNTRY',
#     'PERSTATE',
#     'PERCITY',
#     'PERPINCODE',
#     'COMMDERIVATIVES',
#     'OPTEDFORNOMINATION',
#     'EGR',
#     'BENEFICIALOWNACNTNO1',
#     'OPTED_FOR_UPI',
#     'BANKBRANCHIFSCCODE1',
#     'PRIMARYORSECONDARYBANK1',
#     'BANKBRANCHIFSCCODE2',
#     'PRIMARYORSECONDARYBANK2',
#     'BANKBRANCHIFSCCODE3',
#     'PRIMARYORSECONDARYBANK3',
#     'BANKBRANCHIFSCCODE4',
#     'BANKNAME4',
#     'ACCOUNTNO4',
#     'PRIMARYORSECONDARYBANK4',
#     'BANKBRANCHIFSCCODE5',
#     'BANKNAME5',
#     'ACCOUNTNO5',
#     'PRIMARYORSECONDARYBANK5',
#     'PRIMARYORSECONDARYDP1',
#     'CLIENTNAMEDESCRIPTION',
# }

# # Field shorthands
# def _bsestr(col, **kw):
#     kw.setdefault('max_length', BSE_COLUMN_MAX_LENGTHS[col])
#     db_column = kw.pop('db_column', col)
#     required = col in BSE_MANDATORY_COLUMNS
#     if required:
#         kw.setdefault('default', '')
#     return models.TextField(null=not required, blank=not required, db_column=db_column, **kw)

# def _bsepk(col):
#     return models.BigAutoField(primary_key=True, db_column=col)

# class Bse(models.Model):
#     ID                        = _bsepk('ID')
#     TRANSACTIONCODE           = _bsestr('TRANSACTIONCODE')
#     CLIENTTYPE                = _bsestr('CLIENTTYPE')
#     STATUS                    = _bsestr('STATUS')
#     CATEGORY                  = _bsestr('CATEGORY')
#     CLIENTCODE                = _bsestr('CLIENTCODE')
#     PANNO                     = _bsestr('PANNO')
#     POLITICALEXPERSON         = _bsestr('POLITICALEXPERSON')
#     ADDRESS1                  = _bsestr('ADDRESS1')
#     PERMNEQUALCORP            = _bsestr('PERMNEQUALCORP')
#     ADDRESS2                  = _bsestr('ADDRESS2')
#     COUNTRY                   = _bsestr('COUNTRY')
#     STATE                     = _bsestr('STATE')
#     CITY                      = _bsestr('CITY')
#     PINCODE                   = _bsestr('PINCODE')
#     TYPEOFSERVICE             = _bsestr('TYPEOFSERVICE')
#     CONTACTDETAILS            = _bsestr('CONTACTDETAILS')
#     EMAIL                     = _bsestr('EMAIL')
#     MOBILENUMBER              = _bsestr('MOBILENUMBER')
#     STDCODE                   = _bsestr('STDCODE')
#     PHONENO                   = _bsestr('PHONENO')
#     EQ_CPCODE                 = _bsestr('EQ_CPCODE')
#     EQCMID                    = _bsestr('EQCMID')
#     FNOCPCODE                 = _bsestr('FNOCPCODE')
#     FNOCMID                   = _bsestr('FNOCMID')
#     DEPOSITORYNAME1           = _bsestr('DEPOSITORYNAME1')
#     DEMANTID1                 = _bsestr('DEMANTID1')
#     DEPOSITORYPARTICIPANT1    = _bsestr('DEPOSITORYPARTICIPANT1')
#     DEPOSITORYNAME2           = _bsestr('DEPOSITORYNAME2')
#     DEMANTID2                 = _bsestr('DEMANTID2')
#     DEPOSITORYPARTICIPANT2    = _bsestr('DEPOSITORYPARTICIPANT2')
#     DEPOSITORYNAME3           = _bsestr('DEPOSITORYNAME3')
#     DEMANTID3                 = _bsestr('DEMANTID3')
#     DEPOSITORYPARTICIPANT3    = _bsestr('DEPOSITORYPARTICIPANT3')
#     BANKNAME1                 = _bsestr('BANKNAME1')
#     ACCOUNTNO1                = _bsestr('ACCOUNTNO1')
#     BANKNAME2                 = _bsestr('BANKNAME2')
#     ACCOUNTNO2                = _bsestr('ACCOUNTNO2')
#     BANKNAME3                 = _bsestr('BANKNAME3')
#     ACCOUNTNO3                = _bsestr('ACCOUNTNO3')
#     CLIENTAGGREMENTDATE       = _bsestr('CLIENTAGGREMENTDATE')
#     PROVIDEDETAILS            = _bsestr('PROVIDEDETAILS')
#     INCOME                    = _bsestr('INCOME')
#     INCOMEDATE                = _bsestr('INCOMEDATE')
#     NETWORTH                  = _bsestr('NETWORTH')
#     NETWORTHDATE              = _bsestr('NETWORTHDATE')
#     ISACTIVE                  = _bsestr('ISACTIVE')
#     UPDATEREASON              = _bsestr('UPDATEREASON')
#     FIRSTNAME                 = _bsestr('FIRSTNAME')
#     MIDDLENAME                = _bsestr('MIDDLENAME')
#     LASTNAME                  = _bsestr('LASTNAME')
#     AADHARCARDNO              = _bsestr('AADHARCARDNO')
#     DATEOFBIRTH               = _bsestr('DATEOFBIRTH')
#     CLIENTNAME                = _bsestr('CLIENTNAME')
#     REGISTRATIONNO            = _bsestr('REGISTRATIONNO')
#     REGISTERINGAUTHORITY      = _bsestr('REGISTERINGAUTHORITY')
#     DATEOFREGISTRATION        = _bsestr('DATEOFREGISTRATION')
#     PLACEOFREGISTRATION       = _bsestr('PLACEOFREGISTRATION')
#     WHETHERCORPORATE          = _bsestr('WHETHERCORPORATE')
#     CINNO                     = _bsestr('CINNO')
#     NUMBEROFDIRECTORS         = _bsestr('NUMBEROFDIRECTORS')
#     PARTNERS_KARTAUID         = _bsestr('PARTNERS_KARTAUID')
#     PARTNERS_COPARCENERUID    = _bsestr('PARTNERS_COPARCENERUID')
#     CONTACTPERSONNAME1        = _bsestr('CONTACTPERSONNAME1')
#     CONTACTPERSONDESIGNATION1 = _bsestr('CONTACTPERSONDESIGNATION1')
#     CONTACTPERSONADDRESS1     = _bsestr('CONTACTPERSONADDRESS1')
#     CONTACTPERSONEMAIL1       = _bsestr('CONTACTPERSONEMAIL1')
#     CONTACTPERSONPAN1         = _bsestr('CONTACTPERSONPAN1')
#     CONTACTPERSONMOBILE1      = _bsestr('CONTACTPERSONMOBILE1')
#     CONTACTPERSONNAME2        = _bsestr('CONTACTPERSONNAME2')
#     CONTACTPERSONDESIGNATION2 = _bsestr('CONTACTPERSONDESIGNATION2')
#     CONTACTPERSONADDRESS2     = _bsestr('CONTACTPERSONADDRESS2')
#     CONTACTPERSONEMAIL2       = _bsestr('CONTACTPERSONEMAIL2')
#     CONTACTPERSONPAN2         = _bsestr('CONTACTPERSONPAN2')
#     CONTACTPERSONMOBILE2      = _bsestr('CONTACTPERSONMOBILE2')
#     SERVERIP                  = _bsestr('SERVERIP')
#     BATUSER                   = _bsestr('BATUSER')
#     CASH                      = _bsestr('CASH')
#     EQUITY_DERIVATIVE         = _bsestr('EQUITY_DERIVATIVE')
#     SLB                       = _bsestr('SLB')
#     CURRENCY                  = _bsestr('CURRENCY')
#     DEBT                      = _bsestr('DEBT')
#     ISPOA                     = _bsestr('ISPOA')
#     POAFORFUND                = _bsestr('POAFORFUND')
#     POAFORSECURITY            = _bsestr('POAFORSECURITY')
#     DATEOFPOAFORFUND          = _bsestr('DATEOFPOAFORFUND')
#     DATEOFPOAFORSECURITY      = _bsestr('DATEOFPOAFORSECURITY')
#     PERCOUNTRY                = _bsestr('PERCOUNTRY')
#     PERSTATE                  = _bsestr('PERSTATE')
#     PERCITY                   = _bsestr('PERCITY')
#     PERPINCODE                = _bsestr('PERPINCODE')
#     CURRENCYCPCODE            = _bsestr('CURRENCYCPCODE')
#     CURRENCYCMID              = _bsestr('CURRENCYCMID')
#     ENROLLMENTNUMBER          = _bsestr('ENROLLMENTNUMBER')
#     COMMDERIVATIVES           = _bsestr('COMMDERIVATIVES')
#     OPTEDFORNOMINATION        = _bsestr('OPTEDFORNOMINATION')
#     CUSTPANNO                 = _bsestr('CUSTPANNO')
#     CUSTNAME                  = _bsestr('CUSTNAME')
#     CUSTADDRESS               = _bsestr('CUSTADDRESS')
#     CUSTCOUNTRY               = _bsestr('CUSTCOUNTRY')
#     CUSTSTATE                 = _bsestr('CUSTSTATE')
#     CUSTCITY                  = _bsestr('CUSTCITY')
#     CUSTPINCODE               = _bsestr('CUSTPINCODE')
#     CUSTMOBILENUMBER          = _bsestr('CUSTMOBILENUMBER')
#     CUSTSTDCODE               = _bsestr('CUSTSTDCODE')
#     CUSTPHONENO               = _bsestr('CUSTPHONENO')
#     CUSTEMAIL                 = _bsestr('CUSTEMAIL')
#     EGR                       = _bsestr('EGR')
#     BENEFICIALOWNACNTNO1      = _bsestr('BENEFICIALOWNACNTNO1')
#     BENEFICIALOWNACNTNO2      = _bsestr('BENEFICIALOWNACNTNO2')
#     BENEFICIALOWNACNTNO3      = _bsestr('BENEFICIALOWNACNTNO3')
#     OPTED_FOR_UPI             = _bsestr('OPTED_FOR_UPI')
#     BANKBRANCHIFSCCODE1       = _bsestr('BANKBRANCHIFSCCODE1')
#     PRIMARYORSECONDARYBANK1   = _bsestr('PRIMARYORSECONDARYBANK1')
#     BANKBRANCHIFSCCODE2       = _bsestr('BANKBRANCHIFSCCODE2')
#     PRIMARYORSECONDARYBANK2   = _bsestr('PRIMARYORSECONDARYBANK2')
#     BANKBRANCHIFSCCODE3       = _bsestr('BANKBRANCHIFSCCODE3')
#     PRIMARYORSECONDARYBANK3   = _bsestr('PRIMARYORSECONDARYBANK3')
#     BANKBRANCHIFSCCODE4       = _bsestr('BANKBRANCHIFSCCODE4')
#     BANKNAME4                 = _bsestr('BANKNAME4')
#     ACCOUNTNO4                = _bsestr('ACCOUNTNO4')
#     PRIMARYORSECONDARYBANK4   = _bsestr('PRIMARYORSECONDARYBANK4')
#     BANKBRANCHIFSCCODE5       = _bsestr('BANKBRANCHIFSCCODE5')
#     BANKNAME5                 = _bsestr('BANKNAME5')
#     ACCOUNTNO5                = _bsestr('ACCOUNTNO5')
#     PRIMARYORSECONDARYBANK5   = _bsestr('PRIMARYORSECONDARYBANK5')
#     PRIMARYORSECONDARYDP1     = _bsestr('PRIMARYORSECONDARYDP1')
#     PRIMARYORSECONDARYDP2     = _bsestr('PRIMARYORSECONDARYDP2')
#     PRIMARYORSECONDARYDP3     = _bsestr('PRIMARYORSECONDARYDP3')
#     DEPOSITORYNAME4           = _bsestr('DEPOSITORYNAME4')
#     DEMANTID4                 = _bsestr('DEMANTID4')
#     BENEFICIALOWNACNTNO4      = _bsestr('BENEFICIALOWNACNTNO4')
#     PRIMARYORSECONDARYDP4     = _bsestr('PRIMARYORSECONDARYDP4')
#     DEPOSITORYNAME5           = _bsestr('DEPOSITORYNAME5')
#     DEMANTID5                 = _bsestr('DEMANTID5')
#     BENEFICIALOWNACNTNO5      = _bsestr('BENEFICIALOWNACNTNO5')
#     PRIMARYORSECONDARYDP5     = _bsestr('PRIMARYORSECONDARYDP5')
#     CLIENTNAMEDESCRIPTION     = _bsestr('CLIENTNAMEDESCRIPTION')
#     DIRECTORDETAILS           = _bsestr('DIRECTORDETAILS')

#     class Meta:
#         db_table = 'bse'

#     def __str__(self):
#         return f"{self.CLIENTCODE or self.ID}"


# # BSE Star MF keeps a fixed pipe-delimited UCC record. These are the
# # configurable/default values used for fields that do not come from
# # UserDetails. Keeping the lengths here makes the master screen and model
# # schema work the same way as the other exchange masters.
# BSE_STAR_MF_COLUMN_MAX_LENGTHS = {
#     'tax_status': 2,
#     'holding_nature': 2,
#     'client_type': 1,
#     'pms': 1,
#     'div_pay_mode': 2,
#     'communication_mode': 1,
#     'foreign_address_1': 40,
#     'foreign_address_2': 40,
#     'foreign_address_3': 40,
#     'foreign_city': 35,
#     'foreign_pincode': 10,
#     'foreign_state': 35,
#     'foreign_country': 3,
#     'paperless_flag': 1,
#     'aadhar_seeding_status': 1,
#     'mapin_id': 20,
#     'lei_no': 20,
#     'lei_validity': 20,
#     'primary_pan_holder_exempt': 1,
#     'second_pan_holder_exempt': 1,
#     'third_pan_holder_exempt': 1,
#     'guardian_pan_holder_exempt': 1,
#     'primary_pan_holder_exempt_category': 2,
#     'second_pan_holder_exempt_category': 2,
#     'third_pan_holder_exempt_category': 2,
#     'guardian_pan_holder_exempt_category': 2,
#     'primary_holder_kyc_type': 1,
#     'primary_holder_ckyc_number': 20,
#     'second_holder_kyc_type': 1,
#     'second_holder_ckyc_number': 20,
#     'third_holder_kyc_type': 1,
#     'third_holder_ckyc_number': 20,
#     'guardian_holder_kyc_type': 1,
#     'guardian_holder_ckyc_number': 20,
#     'primary_holder_kra_exempt_ref_number': 20,
#     'second_holder_kra_exempt_ref_number': 20,
#     'third_holder_kra_exempt_ref_number': 20,
#     'guardian_holder_kra_exempt_ref_number': 20,
#     'mobile_declaration_flag': 2,
#     'email_declaration_flag': 2,
#     'guardian_relationship': 40,
#     'nominee_auth_mode': 1,
#     'registration_type': 10,
#     'filler1': 10,
#     'filler2': 10,
#     'filler3': 10,
# }

# BSE_STAR_MF_MANDATORY_COLUMNS = {
#     'tax_status',
#     'holding_nature',
#     'client_type',
#     'div_pay_mode',
#     'communication_mode',
#     'paperless_flag',
#     'primary_holder_kyc_type',
#     'nominee_auth_mode',
#     'registration_type',
# }

# def _bsestarmfstr(col, **kw):
#     kw.setdefault('max_length', BSE_STAR_MF_COLUMN_MAX_LENGTHS[col])
#     db_column = kw.pop('db_column', col)
#     required = col in BSE_STAR_MF_MANDATORY_COLUMNS
#     if required:
#         kw.setdefault('default', '')
#     return models.CharField(null=not required, blank=not required, db_column=db_column, **kw)

# class BseStarMf(models.Model):
#     """Editable defaults for the BSE Star MF UCC pipe record."""

#     id = _bsepk('id')
#     tax_status = _bsestarmfstr('tax_status', default='01')
#     holding_nature = _bsestarmfstr('holding_nature', default='SI')
#     client_type = _bsestarmfstr('client_type', default='P')
#     pms = _bsestarmfstr('pms', default='')
#     div_pay_mode = _bsestarmfstr('div_pay_mode', default='02')
#     communication_mode = _bsestarmfstr('communication_mode', default='E')
#     foreign_address_1 = _bsestarmfstr('foreign_address_1', default='')
#     foreign_address_2 = _bsestarmfstr('foreign_address_2', default='')
#     foreign_address_3 = _bsestarmfstr('foreign_address_3', default='')
#     foreign_city = _bsestarmfstr('foreign_city', default='')
#     foreign_pincode = _bsestarmfstr('foreign_pincode', default='')
#     foreign_state = _bsestarmfstr('foreign_state', default='')
#     foreign_country = _bsestarmfstr('foreign_country', default='')
#     paperless_flag = _bsestarmfstr('paperless_flag', default='Z')
#     aadhar_seeding_status = _bsestarmfstr('aadhar_seeding_status', default='')
#     mapin_id = _bsestarmfstr('mapin_id', default='')
#     lei_no = _bsestarmfstr('lei_no', default='')
#     lei_validity = _bsestarmfstr('lei_validity', default='')
#     primary_pan_holder_exempt = _bsestarmfstr('primary_pan_holder_exempt', default='N')
#     second_pan_holder_exempt = _bsestarmfstr('second_pan_holder_exempt', default='')
#     third_pan_holder_exempt = _bsestarmfstr('third_pan_holder_exempt', default='')
#     guardian_pan_holder_exempt = _bsestarmfstr('guardian_pan_holder_exempt', default='')
#     primary_pan_holder_exempt_category = _bsestarmfstr('primary_pan_holder_exempt_category', default='')
#     second_pan_holder_exempt_category = _bsestarmfstr('second_pan_holder_exempt_category', default='')
#     third_pan_holder_exempt_category = _bsestarmfstr('third_pan_holder_exempt_category', default='')
#     guardian_pan_holder_exempt_category = _bsestarmfstr('guardian_pan_holder_exempt_category', default='')
#     primary_holder_kyc_type = _bsestarmfstr('primary_holder_kyc_type', default='K')
#     primary_holder_ckyc_number = _bsestarmfstr('primary_holder_ckyc_number', default='')
#     second_holder_kyc_type = _bsestarmfstr('second_holder_kyc_type', default='')
#     second_holder_ckyc_number = _bsestarmfstr('second_holder_ckyc_number', default='')
#     third_holder_kyc_type = _bsestarmfstr('third_holder_kyc_type', default='')
#     third_holder_ckyc_number = _bsestarmfstr('third_holder_ckyc_number', default='')
#     guardian_holder_kyc_type = _bsestarmfstr('guardian_holder_kyc_type', default='')
#     guardian_holder_ckyc_number = _bsestarmfstr('guardian_holder_ckyc_number', default='')
#     primary_holder_kra_exempt_ref_number = _bsestarmfstr('primary_holder_kra_exempt_ref_number', default='')
#     second_holder_kra_exempt_ref_number = _bsestarmfstr('second_holder_kra_exempt_ref_number', default='')
#     third_holder_kra_exempt_ref_number = _bsestarmfstr('third_holder_kra_exempt_ref_number', default='')
#     guardian_holder_kra_exempt_ref_number = _bsestarmfstr('guardian_holder_kra_exempt_ref_number', default='')
#     mobile_declaration_flag = _bsestarmfstr('mobile_declaration_flag', default='SE')
#     email_declaration_flag = _bsestarmfstr('email_declaration_flag', default='SE')
#     guardian_relationship = _bsestarmfstr('guardian_relationship', default='')
#     nominee_auth_mode = _bsestarmfstr('nominee_auth_mode', default='O')
#     registration_type = _bsestarmfstr('registration_type', default='NEW')
#     filler1 = _bsestarmfstr('filler1', default='')
#     filler2 = _bsestarmfstr('filler2', default='')
#     filler3 = _bsestarmfstr('filler3', default='')

#     class Meta:
#         db_table = 'bse_star_mf'

#     def __str__(self):
#         return str(self.id)


# class BseStarMfDependencyMaster(models.Model):
#     dependency = models.CharField(max_length=100, unique=True, db_column='dependency')
#     dependency_code = models.CharField(max_length=10, db_column='dependency_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'bse_star_mf_dependency_master'
#         ordering = ('dependency',)

#     def __str__(self):
#         return f"{self.dependency} - {self.dependency_code}"


# class BseStarMfGenderMaster(models.Model):
#     gender = models.CharField(max_length=50, unique=True, db_column='gender')
#     gender_code = models.CharField(max_length=10, db_column='gender_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'bse_star_mf_gender_master'
#         ordering = ('gender',)

#     def __str__(self):
#         return f"{self.gender} - {self.gender_code}"


# class BseStarMfStateCodeMaster(models.Model):
#     state_name = models.CharField(max_length=100, unique=True, db_column='state_name')
#     state_code = models.CharField(max_length=10, db_column='state_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'bse_star_mf_state_code_master'
#         ordering = ('state_name',)

#     def __str__(self):
#         return f"{self.state_name} - {self.state_code}"


# class BseStarMfTaxStatusMaster(models.Model):
#     tax_status = models.CharField(max_length=100, unique=True, db_column='tax_status')
#     tax_code = models.CharField(max_length=10, db_column='tax_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'bse_star_mf_tax_status_master'
#         ordering = ('tax_status',)

#     def __str__(self):
#         return f"{self.tax_status} - {self.tax_code}"


# NSE_COLUMN_MAX_LENGTHS = {
#     'ccdMemCd': 50,
#     'ccdCd': 50,
#     'ccdName': 50,
#     'ccdCategory': 50,
#     'ccdPinCode': 50,
#     'ccdTelNo': 50,
#     'ccdTvFlag': 50,
#     'ccdAgrDt': 50,
#     'ccdPanNo': 50,
#     'ccdRegNo': 50,
#     'ccdRegAuth': 50,
#     'ccdPlcReg': 50,
#     'ccdDtReg': 50,
#     'ccdSegInd': 50,
#     'ccdDob': 50,
#     'ccdBankBrAdd': 50,
#     'ccdDeposId': 50,
#     'ccdAddLine1': 50,
#     'ccdAddLine2': 50,
#     'ccdAddLine3': 50,
#     'ccdAddCity': 50,
#     'ccdAddState': 50,
#     'ccdAddCountry': 50,
#     'ccdTelIsd': 50,
#     'ccdTelStd': 50,
#     'ccdMobile': 50,
#     'ccdEmail': 50,
#     'ccdProofType': 50,
#     'ccdProofNo': 50,
#     'ccdIssPlcProof': 50,
#     'ccdIssDtProof': 50,
#     'ccdDir1Name': 50,
#     'ccdDir2Name': 50,
#     'ccdDir3Name': 50,
#     'ccdDir1Desig': 50,
#     'ccdDir2Desig': 50,
#     'ccdDir3Desig': 50,
#     'ccdDir1Pan': 50,
#     'ccdDir2Pan': 50,
#     'ccdDir3Pan': 50,
#     'ccdDir1Add': 50,
#     'ccdDir2Add': 50,
#     'ccdDir3Add': 50,
#     'ccdDir1TelNo': 50,
#     'ccdDir2TelNo': 50,
#     'ccdDir3TelNo': 50,
#     'ccdDir1Email': 50,
#     'ccdDir2Email': 50,
#     'ccdDir3Email': 50,
#     'ccdIpv': 50,
#     'ccdUccCd': 50,
#     'ccdRelationship': 50,
#     'ccdFacilityType': 50,
#     'ccdCin': 50,
#     'ccdCltStatus': 50,
#     'ccdCltStatusReason': 50,
#     'ccdGender': 50,
#     'ccdGuardianName': 50,
#     'ccdMaritlStatus': 50,
#     'ccdNationality': 50,
#     'ccdPermantAddFlg': 50,
#     'ccdPermAddLine1': 50,
#     'ccdPermAddLine2': 50,
#     'ccdPermAddLine3': 50,
#     'ccdPermAddCity': 50,
#     'ccdPermAddState': 50,
#     'ccdPermAddCountry': 50,
#     'ccdPermPin': 50,
#     'ccdOffcIsd': 50,
#     'ccdOffcStd': 50,
#     'ccdTelOffice': 50,
#     'ccdUid': 50,
#     'ccdDeposName': 50,
#     'ccdBankName': 50,
#     'ccdBankAcctNo': 50,
#     'ccdBenAcctNo': 50,
#     'ccdBankName2': 50,
#     'ccdBankAcctNo2': 50,
#     'ccdBankName3': 50,
#     'ccdBankAcctNo3': 50,
#     'ccdDeposName2': 50,
#     'ccdDeposId2': 50,
#     'ccdBenAcctNo2': 50,
#     'ccdDeposName3': 50,
#     'ccdDeposId3': 50,
#     'ccdBenAcctNo3': 50,
#     'ccdGrosAnnlRnge': 50,
#     'ccdGrosAnnlAsdate': 50,
#     'ccdNetWorth': 50,
#     'ccdNetWorthAsdate': 50,
#     'ccdPep': 50,
#     'ccdPoi': 50,
#     'ccdOccupation': 50,
#     'ccdOccupationDtls': 50,
#     'ccdBusComDt': 50,
#     'ccdCpCd': 50,
#     'ccdClntTyp': 50,
#     'ccdDinCntrctPerson1': 50,
#     'ccdUidCntrctPerson1': 50,
#     'ccdDinCntrctPerson2': 50,
#     'ccdUidCntrctPerson2': 50,
#     'ccdDinCntrctPerson3': 50,
#     'ccdUidCntrctPerson3': 50,
#     'ccdDir4Name': 50,
#     'ccdDir4Desig': 50,
#     'ccdDir4Pan': 50,
#     'ccdDir4Add': 50,
#     'ccdDir4TelNo': 50,
#     'ccdDinCntrctPerson4': 50,
#     'ccdUidCntrctPerson4': 50,
#     'ccdDir4Email': 50,
#     'ccdDir5Name': 50,
#     'ccdDir5Desig': 50,
#     'ccdDir5Pan': 50,
#     'ccdDir5Add': 50,
#     'ccdDir5TelNo': 50,
#     'ccdDinCntrctPerson5': 50,
#     'ccdUidCntrctPerson5': 50,
#     'ccdDir5Email': 50,
#     'ccdNationalityOth': 50,
#     'ccdPermAddStateOth': 50,
#     'ccdAddStateOth': 50,
#     'ccdPoaFunds': 50,
#     'ccdPoaSecurities': 50,
#     'ccdNomFlag': 50,
#     'ccdCpName': 50,
#     'ccdCpPan': 50,
#     'ccdCpEmail': 50,
#     'ccdCpStd': 50,
#     'ccdCpIsd': 50,
#     'ccdCpTel': 50,
#     'ccdCpMob': 50,
#     'ccdCpAdd': 50,
#     'ccdCpAddCity': 50,
#     'ccdCpAddState': 50,
#     'ccdCpAddStateOth': 50,
#     'ccdCpAddCountry': 50,
#     'ccdCpAddPin': 50,
#     'ccdBankIfsc': 50,
#     'ccdBankIfsc2': 50,
#     'ccdBankIfsc3': 50,
#     'ccdBankIfsc4': 50,
#     'ccdBankIfsc5': 50,
#     'ccdPriSecBnk': 50,
#     'ccdPriSecBnk2': 50,
#     'ccdPriSecBnk3': 50,
#     'ccdPriSecBnk4': 50,
#     'ccdPriSecBnk5': 50,
#     'ccdPriSecDp': 50,
#     'ccdPriSecDp2': 50,
#     'ccdPriSecDp3': 50,
#     'ccdPriSecDp4': 50,
#     'ccdPriSecDp5': 50,
#     'ccdAcctType': 50,
#     'ccdOptForUpi': 50,
#     'ccdBankName4': 50,
#     'ccdBankAcctNo4': 50,
#     'ccdBankName5': 50,
#     'ccdBankAcctNo5': 50,
#     'ccdDeposName4': 50,
#     'ccdDeposId4': 50,
#     'ccdBenAcctNo4': 50,
#     'ccdDeposName5': 50,
#     'ccdDeposId5': 50,
#     'ccdBenAcctNo5': 50,
#     'ccdBankBrAdd': 50,
#     'ccdAddLine1': 50,
#     'ccdAddLine2': 50,
#     'ccdAddLine3': 50,
#     'ccdDir1Add': 50,
#     'ccdDir2Add': 50,
#     'ccdDir3Add': 50,
#     'ccdPermAddLine1': 50,
#     'ccdPermAddLine2': 50,
#     'ccdPermAddLine3': 50,
#     'ccdDir4Add': 50,
#     'ccdDir5Add': 50,
# }

# NSE_MANDATORY_COLUMNS = {
#     'ccdAcctType',
#     'ccdAddCity',
#     'ccdAddCountry',
#     'ccdAddLine1',
#     'ccdAddLine2',
#     'ccdAddLine3',
#     'ccdAddState',
#     'ccdAgrDt',
#     'ccdBankAcctNo',
#     'ccdBankAcctNo2',
#     'ccdBankAcctNo3',
#     'ccdBankAcctNo4',
#     'ccdBankAcctNo5',
#     'ccdBankBrAdd',
#     'ccdBankIfsc',
#     'ccdBankIfsc2',
#     'ccdBankIfsc3',
#     'ccdBankIfsc4',
#     'ccdBankIfsc5',
#     'ccdBankName',
#     'ccdBankName2',
#     'ccdBankName3',
#     'ccdBankName4',
#     'ccdBankName5',
#     'ccdBenAcctNo',
#     'ccdCategory',
#     'ccdCd',
#     'ccdClntTyp',
#     'ccdCltStatus',
#     'ccdCltStatusReason',
#     'ccdDeposId',
#     'ccdDeposName',
#     'ccdDob',
#     'ccdEmail',
#     'ccdGender',
#     'ccdGrosAnnlAsdate',
#     'ccdGrosAnnlRnge',
#     'ccdGuardianName',
#     'ccdIpv',
#     'ccdMaritlStatus',
#     'ccdMemCd',
#     'ccdMobile',
#     'ccdName',
#     'ccdNationality',
#     'ccdNetWorth',
#     'ccdNetWorthAsdate',
#     'ccdNomFlag',
#     'ccdOccupation',
#     'ccdOptForUpi',
#     'ccdPanNo',
#     'ccdPep',
#     'ccdPermAddCity',
#     'ccdPermAddCountry',
#     'ccdPermAddLine1',
#     'ccdPermAddLine2',
#     'ccdPermAddLine3',
#     'ccdPermAddState',
#     'ccdPermPin',
#     'ccdPermantAddFlg',
#     'ccdPinCode',
#     'ccdPoaFunds',
#     'ccdPoaSecurities',
#     'ccdPriSecBnk',
#     'ccdPriSecBnk2',
#     'ccdPriSecBnk3',
#     'ccdPriSecBnk4',
#     'ccdPriSecBnk5',
#     'ccdPriSecDp',
#     'ccdSegInd',
# }

# # MSE uses the same editable-master pattern as NSE and BSE.  The API accepts
# # one JSON object containing these 283 fields; values that are specific to a
# # client are replaced from UserDetails when the request is built, while the
# # table keeps the provider's fixed/default columns visible in Master.
# MSE_BASE_COLUMNS = (
#     'ccdECM', 'ccdEDS', 'ccdCDS', 'ccdClientCode', 'ccdClientName',
#     'ccdAccountType', 'ccdCategory', 'ccdPANNo', 'ccdGender',
#     'ccdGuardianName', 'ccdNationality', 'ccdEmailID',
#     'ccdRelationshipWithClientForEmail', 'ccdCorrespondenceClientAddress',
#     'ccdCorrespondenceClientCity', 'ccdCorrespondenceClientState',
#     'ccdCorrespondenceClientOtherState', 'ccdCorrespondenceClientCountry',
#     'ccdCorrespondenceClientPinCode', 'ccdPermanentAddSameAsCorrs',
#     'ccdPermanentAddress', 'ccdPermanentCity', 'ccdPermanentState',
#     'ccdPermanentOtherState', 'ccdPermanentCountryCode',
#     'ccdPermanentPincode', 'ccdMobileNo',
#     'ccdRelationshipWithClientForMobile', 'ccdOfficeTelephoneNo',
#     'ccdISDCode', 'ccdSTDCode', 'ccdDateofBirth', 'ccdUID', 'ccdBankName1',
#     'ccdIFSCCode1', 'ccdBankAccountNo1', 'ccdBankAccountType1',
#     'ccdPrimarySecondaryBank1', 'ccdCINOfClient',
#     'ccdGrossAnnualIncomeRange', 'ccdGrossAnnualIncomeDate', 'ccdNetworth',
#     'ccdNetworthAsOnDate', 'ccdPEPersopn', 'ccdOccupation',
#     'ccdOccupationDetails', 'ccdCPCodeECM', 'ccdCPCodeEDS', 'ccdCPCodeCDS',
#     'ccdRegistrationNo', 'ccdRegisteringAuthority', 'ccdRegistrationPlace',
#     'ccdRegistrationDate', 'ccdInpersonVerification', 'ccdAgreementDate',
#     'ccdTypeOfFacility', 'ccdUpdationFlagSMSEmail', 'ccdRelationshipCode',
#     'ccdProofType', 'ccdProofNo', 'ccdPlaceOfProof', 'ccdIssueProofDate',
#     'ccdStatus', 'ccdClientTypeCorporate', 'ccdPOAFunds', 'ccdPOASecurities',
#     'ccdPOAFundsDate', 'ccdPOASecuritiesDate', 'ccdDDPISettlement',
#     'ccdDDPISettlementDate', 'ccdDDPIPledging', 'ccdDDPIPledgingDate',
#     'ccdNominationOption', 'ccdUPIOpt', 'ccdClientNameDescription', 'ccdFlag',
# )
# MSE_BANK_COLUMNS = tuple(
#     f'{prefix}{number}'
#     for number in range(2, 11)
#     for prefix in (
#         'ccdBankName', 'ccdIFSCCode', 'ccdBankAccountNo',
#         'ccdBankAccountType', 'ccdPrimarySecondaryBank',
#     )
# )
# MSE_DEPOSITORY_COLUMNS = tuple(
#     f'{prefix}{number}'
#     for number in range(1, 6)
#     for prefix in (
#         'ccdDepositoryName', 'ccdDepositoryId', 'ccdBeneficiaryAccountNo',
#         'ccdPrimarySecondaryDP',
#     )
# )
# MSE_PROVIDER_CONTACT_COLUMNS = tuple(
#     f'ccd{provider}{suffix}'
#     for provider in ('ECM', 'EDS', 'CDS')
#     for suffix in (
#         'CPName', 'CPPANNo', 'CPEmailId', 'CorrespondenceCPAddress',
#         'CorrespondenceCPCity', 'CorrespondenceCPState',
#         'CorrespondenceCPOtherState', 'CorrespondenceCPCountry',
#         'CorrespondenceCPPinCode', 'CPMobileNo', 'CPISDCode', 'CPSTDCode',
#         'CPTelephoneNo',
#     )
# )
# MSE_CONTACT_COLUMNS = tuple(
#     f'ccdCP{suffix}{number}'
#     for number in range(1, 7)
#     for suffix in (
#         'Name', 'Designation', 'PANNo', 'Address', 'ContactDetails', 'DIN',
#         'EmailID',
#     )
# )
# MSE_COLUMNS = (
#     *(f'ccdReserved{number}' for number in range(1, 62)),
#     *MSE_BASE_COLUMNS,
#     *MSE_BANK_COLUMNS,
#     *MSE_DEPOSITORY_COLUMNS,
#     *MSE_PROVIDER_CONTACT_COLUMNS,
#     *MSE_CONTACT_COLUMNS,
# )
# # Temporary string size for the wide MSE table.  The table has 283 columns;
# # keeping the initial width small avoids MySQL's InnoDB row-size limit.  Set
# # larger lengths only on the fields that need them after the table exists.
# MSE_COLUMN_MAX_LENGTHS = {column: 20 for column in MSE_COLUMNS}


# def _msepk(col):
#     return models.BigAutoField(primary_key=True, db_column=col)


# def _msestr(col, **kw):
#     kw.setdefault('max_length', MSE_COLUMN_MAX_LENGTHS[col])
#     db_column = kw.pop('db_column', col)
#     return models.TextField(null=True, blank=True, db_column=db_column, **kw)


# class Mse(models.Model):
#     """Editable defaults/schema for the MSE JSON UCC payload."""

#     id = _msepk('id')
#     locals().update({column: _msestr(column) for column in MSE_COLUMNS})

#     class Meta:
#         db_table = 'mse'

#     def __str__(self):
#         return f'MSE defaults {self.id}'


# class MseStateCodeMaster(models.Model):
#     state_name = models.CharField(max_length=100, unique=True)
#     state_code = models.CharField(max_length=6)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'mse_state_code_master'
#         ordering = ('state_name',)


# class MseOccupationMaster(models.Model):
#     occupation_name = models.CharField(max_length=50, unique=True)
#     occupation_code = models.CharField(max_length=10)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'mse_occupation_master'
#         ordering = ('occupation_name',)


# class MseIncomeRangeMaster(models.Model):
#     income_range = models.CharField(max_length=50, unique=True)
#     income_code = models.CharField(max_length=10)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'mse_income_range_master'
#         ordering = ('income_range',)


# class MseAccountTypeMaster(models.Model):
#     account_type = models.CharField(max_length=50, unique=True)
#     account_code = models.CharField(max_length=10)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'mse_account_type_master'
#         ordering = ('account_type',)

# def _nsepk(col):
#     return models.BigAutoField(primary_key=True, db_column=col)

# def _nsestr(col, **kw):
#     kw.setdefault('max_length', NSE_COLUMN_MAX_LENGTHS[col])
#     db_column = kw.pop('db_column', col)
#     required = col in NSE_MANDATORY_COLUMNS
#     if required:
#         kw.setdefault('default', '')
#     return models.TextField(null=not required, blank=not required, db_column=db_column, **kw)


# class Nse(models.Model):
#     id                        = _nsepk('id')
#     ccdMemCd                  = _nsestr('ccdMemCd')
#     ccdCd                     = _nsestr('ccdCd')
#     ccdName                   = _nsestr('ccdName')
#     ccdCategory               = _nsestr('ccdCategory')
#     ccdPinCode                = _nsestr('ccdPinCode')
#     ccdTelNo                  = _nsestr('ccdTelNo')
#     ccdTvFlag                 = _nsestr('ccdTvFlag')
#     ccdAgrDt                  = _nsestr('ccdAgrDt')
#     ccdPanNo                  = _nsestr('ccdPanNo')
#     ccdRegNo                  = _nsestr('ccdRegNo')
#     ccdRegAuth                = _nsestr('ccdRegAuth')
#     ccdPlcReg                 = _nsestr('ccdPlcReg')
#     ccdDtReg                  = _nsestr('ccdDtReg')
#     ccdSegInd                 = _nsestr('ccdSegInd')
#     ccdDob                    = _nsestr('ccdDob')
#     ccdBankBrAdd              = _nsestr('ccdBankBrAdd')
#     ccdDeposId                = _nsestr('ccdDeposId')
#     ccdAddLine1               = _nsestr('ccdAddLine1')
#     ccdAddLine2               = _nsestr('ccdAddLine2')
#     ccdAddLine3               = _nsestr('ccdAddLine3')
#     ccdAddCity                = _nsestr('ccdAddCity')
#     ccdAddState               = _nsestr('ccdAddState')
#     ccdAddCountry             = _nsestr('ccdAddCountry')
#     ccdTelIsd                 = _nsestr('ccdTelIsd')
#     ccdTelStd                 = _nsestr('ccdTelStd')
#     ccdMobile                 = _nsestr('ccdMobile')
#     ccdEmail                  = _nsestr('ccdEmail')
#     ccdProofType              = _nsestr('ccdProofType')
#     ccdProofNo                = _nsestr('ccdProofNo')
#     ccdIssPlcProof            = _nsestr('ccdIssPlcProof')
#     ccdIssDtProof             = _nsestr('ccdIssDtProof')
#     ccdDir1Name               = _nsestr('ccdDir1Name')
#     ccdDir2Name               = _nsestr('ccdDir2Name')
#     ccdDir3Name               = _nsestr('ccdDir3Name')
#     ccdDir1Desig              = _nsestr('ccdDir1Desig')
#     ccdDir2Desig              = _nsestr('ccdDir2Desig')
#     ccdDir3Desig              = _nsestr('ccdDir3Desig')
#     ccdDir1Pan                = _nsestr('ccdDir1Pan')
#     ccdDir2Pan                = _nsestr('ccdDir2Pan')
#     ccdDir3Pan                = _nsestr('ccdDir3Pan')
#     ccdDir1Add                = _nsestr('ccdDir1Add')
#     ccdDir2Add                = _nsestr('ccdDir2Add')
#     ccdDir3Add                = _nsestr('ccdDir3Add')
#     ccdDir1TelNo              = _nsestr('ccdDir1TelNo')
#     ccdDir2TelNo              = _nsestr('ccdDir2TelNo')
#     ccdDir3TelNo              = _nsestr('ccdDir3TelNo')
#     ccdDir1Email              = _nsestr('ccdDir1Email')
#     ccdDir2Email              = _nsestr('ccdDir2Email')
#     ccdDir3Email              = _nsestr('ccdDir3Email')
#     ccdIpv                    = _nsestr('ccdIpv')
#     ccdUccCd                  = _nsestr('ccdUccCd')
#     ccdRelationship           = _nsestr('ccdRelationship')
#     ccdFacilityType           = _nsestr('ccdFacilityType')
#     ccdCin                    = _nsestr('ccdCin')
#     ccdCltStatus              = _nsestr('ccdCltStatus')
#     ccdCltStatusReason        = _nsestr('ccdCltStatusReason')
#     ccdGender                 = _nsestr('ccdGender')
#     ccdGuardianName           = _nsestr('ccdGuardianName')
#     ccdMaritlStatus           = _nsestr('ccdMaritlStatus')
#     ccdNationality            = _nsestr('ccdNationality')
#     ccdPermantAddFlg          = _nsestr('ccdPermantAddFlg')
#     ccdPermAddLine1           = _nsestr('ccdPermAddLine1')
#     ccdPermAddLine2           = _nsestr('ccdPermAddLine2')
#     ccdPermAddLine3           = _nsestr('ccdPermAddLine3')
#     ccdPermAddCity            = _nsestr('ccdPermAddCity')
#     ccdPermAddState           = _nsestr('ccdPermAddState')
#     ccdPermAddCountry         = _nsestr('ccdPermAddCountry')
#     ccdPermPin                = _nsestr('ccdPermPin')
#     ccdOffcIsd                = _nsestr('ccdOffcIsd')
#     ccdOffcStd                = _nsestr('ccdOffcStd')
#     ccdTelOffice              = _nsestr('ccdTelOffice')
#     ccdUid                    = _nsestr('ccdUid')
#     ccdDeposName              = _nsestr('ccdDeposName')
#     ccdBankName               = _nsestr('ccdBankName')
#     ccdBankAcctNo             = _nsestr('ccdBankAcctNo')
#     ccdBenAcctNo              = _nsestr('ccdBenAcctNo')
#     ccdBankName2              = _nsestr('ccdBankName2')
#     ccdBankAcctNo2            = _nsestr('ccdBankAcctNo2')
#     ccdBankName3              = _nsestr('ccdBankName3')
#     ccdBankAcctNo3            = _nsestr('ccdBankAcctNo3')
#     ccdDeposName2             = _nsestr('ccdDeposName2')
#     ccdDeposId2               = _nsestr('ccdDeposId2')
#     ccdBenAcctNo2             = _nsestr('ccdBenAcctNo2')
#     ccdDeposName3             = _nsestr('ccdDeposName3')
#     ccdDeposId3               = _nsestr('ccdDeposId3')
#     ccdBenAcctNo3             = _nsestr('ccdBenAcctNo3')
#     ccdGrosAnnlRnge           = _nsestr('ccdGrosAnnlRnge')
#     ccdGrosAnnlAsdate         = _nsestr('ccdGrosAnnlAsdate')
#     ccdNetWorth               = _nsestr('ccdNetWorth')
#     ccdNetWorthAsdate         = _nsestr('ccdNetWorthAsdate')
#     ccdPep                    = _nsestr('ccdPep')
#     ccdPoi                    = _nsestr('ccdPoi')
#     ccdOccupation             = _nsestr('ccdOccupation')
#     ccdOccupationDtls         = _nsestr('ccdOccupationDtls')
#     ccdBusComDt               = _nsestr('ccdBusComDt')
#     ccdCpCd                   = _nsestr('ccdCpCd')
#     ccdClntTyp                = _nsestr('ccdClntTyp')
#     ccdDinCntrctPerson1       = _nsestr('ccdDinCntrctPerson1')
#     ccdUidCntrctPerson1       = _nsestr('ccdUidCntrctPerson1')
#     ccdDinCntrctPerson2       = _nsestr('ccdDinCntrctPerson2')
#     ccdUidCntrctPerson2       = _nsestr('ccdUidCntrctPerson2')
#     ccdDinCntrctPerson3       = _nsestr('ccdDinCntrctPerson3')
#     ccdUidCntrctPerson3       = _nsestr('ccdUidCntrctPerson3')
#     ccdDir4Name               = _nsestr('ccdDir4Name')
#     ccdDir4Desig              = _nsestr('ccdDir4Desig')
#     ccdDir4Pan                = _nsestr('ccdDir4Pan')
#     ccdDir4Add                = _nsestr('ccdDir4Add')
#     ccdDir4TelNo              = _nsestr('ccdDir4TelNo')
#     ccdDinCntrctPerson4       = _nsestr('ccdDinCntrctPerson4')
#     ccdUidCntrctPerson4       = _nsestr('ccdUidCntrctPerson4')
#     ccdDir4Email              = _nsestr('ccdDir4Email')
#     ccdDir5Name               = _nsestr('ccdDir5Name')
#     ccdDir5Desig              = _nsestr('ccdDir5Desig')
#     ccdDir5Pan                = _nsestr('ccdDir5Pan')
#     ccdDir5Add                = _nsestr('ccdDir5Add')
#     ccdDir5TelNo              = _nsestr('ccdDir5TelNo')
#     ccdDinCntrctPerson5       = _nsestr('ccdDinCntrctPerson5')
#     ccdUidCntrctPerson5       = _nsestr('ccdUidCntrctPerson5')
#     ccdDir5Email              = _nsestr('ccdDir5Email')
#     ccdNationalityOth         = _nsestr('ccdNationalityOth')
#     ccdPermAddStateOth        = _nsestr('ccdPermAddStateOth')
#     ccdAddStateOth            = _nsestr('ccdAddStateOth')
#     ccdPoaFunds               = _nsestr('ccdPoaFunds')
#     ccdPoaSecurities          = _nsestr('ccdPoaSecurities')
#     ccdNomFlag                = _nsestr('ccdNomFlag')
#     ccdCpName                 = _nsestr('ccdCpName')
#     ccdCpPan                  = _nsestr('ccdCpPan')
#     ccdCpEmail                = _nsestr('ccdCpEmail')
#     ccdCpStd                  = _nsestr('ccdCpStd')
#     ccdCpIsd                  = _nsestr('ccdCpIsd')
#     ccdCpTel                  = _nsestr('ccdCpTel')
#     ccdCpMob                  = _nsestr('ccdCpMob')
#     ccdCpAdd                  = _nsestr('ccdCpAdd')
#     ccdCpAddCity              = _nsestr('ccdCpAddCity')
#     ccdCpAddState             = _nsestr('ccdCpAddState')
#     ccdCpAddStateOth          = _nsestr('ccdCpAddStateOth')
#     ccdCpAddCountry           = _nsestr('ccdCpAddCountry')
#     ccdCpAddPin               = _nsestr('ccdCpAddPin')
#     ccdBankIfsc               = _nsestr('ccdBankIfsc')
#     ccdBankIfsc2              = _nsestr('ccdBankIfsc2')
#     ccdBankIfsc3              = _nsestr('ccdBankIfsc3')
#     ccdBankIfsc4              = _nsestr('ccdBankIfsc4')
#     ccdBankIfsc5              = _nsestr('ccdBankIfsc5')
#     ccdPriSecBnk              = _nsestr('ccdPriSecBnk')
#     ccdPriSecBnk2             = _nsestr('ccdPriSecBnk2')
#     ccdPriSecBnk3             = _nsestr('ccdPriSecBnk3')
#     ccdPriSecBnk4             = _nsestr('ccdPriSecBnk4')
#     ccdPriSecBnk5             = _nsestr('ccdPriSecBnk5')
#     ccdPriSecDp               = _nsestr('ccdPriSecDp')
#     ccdPriSecDp2              = _nsestr('ccdPriSecDp2')
#     ccdPriSecDp3              = _nsestr('ccdPriSecDp3')
#     ccdPriSecDp4              = _nsestr('ccdPriSecDp4')
#     ccdPriSecDp5              = _nsestr('ccdPriSecDp5')
#     ccdAcctType               = _nsestr('ccdAcctType')
#     ccdOptForUpi              = _nsestr('ccdOptForUpi')
#     ccdBankName4              = _nsestr('ccdBankName4')
#     ccdBankAcctNo4            = _nsestr('ccdBankAcctNo4')
#     ccdBankName5              = _nsestr('ccdBankName5')
#     ccdBankAcctNo5            = _nsestr('ccdBankAcctNo5')
#     ccdDeposName4             = _nsestr('ccdDeposName4')
#     ccdDeposId4               = _nsestr('ccdDeposId4')
#     ccdBenAcctNo4             = _nsestr('ccdBenAcctNo4')
#     ccdDeposName5             = _nsestr('ccdDeposName5')
#     ccdDeposId5               = _nsestr('ccdDeposId5')
#     ccdBenAcctNo5             = _nsestr('ccdBenAcctNo5')

#     class Meta:
#         db_table = 'nse'

#     def __str__(self):
#         return f"{self.ccdCd or self.id}"


# def _credentialbsestr(col, **kw):
#     kw.setdefault('max_length', 50)
#     db_column = kw.pop('db_column', col)
#     return models.CharField(null=True, blank=True, db_column=db_column, **kw)

# class BseCredentials(models.Model):
#     id = models.BigAutoField(primary_key=True, db_column='id')
#     user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, db_column='user_id', related_name='api_credentials')
#     MemberCode = _credentialbsestr('MemberCode')
#     UserID = _credentialbsestr('UserID')
#     Password = _credentialbsestr('Password')
#     type = _credentialbsestr('type')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'bse_credentials'
#         unique_together = (('user', 'type'),)

#     def __str__(self):
#         return f"{self.user_id or self.id} - {self.type}"


# class BseStarMfCredentials(models.Model):
#     """BSE Star MF credentials; one credential set per company/environment."""

#     id = models.BigAutoField(primary_key=True, db_column='id')
#     user = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         null=True,
#         blank=True,
#         on_delete=models.CASCADE,
#         db_column='user_id',
#         related_name='bse_star_mf_credentials',
#     )
#     environment = models.CharField(max_length=10, default='uat')
#     MemberId = models.CharField(max_length=50, blank=True, default='')
#     UserId = models.CharField(max_length=50, blank=True, default='')
#     Password = models.CharField(max_length=50, blank=True, default='')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'bse_star_mf_credentials'
#         unique_together = (('user', 'environment'),)



# CKYC_COLUMN_MAX_LENGTHS = {
#     'record_type': 2,
#     'record_version': 10,
#     'detail_record_type': 2,
#     'detail_version': 2,
#     'detail_flag': 1,
#     'application_type': 2,
#     'kyc_branch': 50,
#     'name_update_flag': 2,
#     'personal_detail_flag': 2,
#     'address_update_flag': 2,
#     'contact_update_flag': 2,
#     'record_status': 2,
#     'ipv_flag': 2,
#     'identity_type': 2,
#     'reference_type': 2,
#     'name_title': 10,
#     'father_title': 10,
#     'mother_title': 10,
#     'gender': 1,
#     'occupation': 50,
#     'nationality': 2,
#     'pan_status': 2,
#     'pan_exempt_flag': 2,
#     'correspondence_country': 3,
#     'correspondence_proof': 2,
#     'permanent_address_flag': 1,
#     'permanent_country': 3,
#     'permanent_proof': 2,
#     'mobile_isd': 5,
#     'application_date': 10,
#     'kyc_mode': 2,
#     'verification_name': 100,
#     'verification_designation': 100,
#     'verification_branch': 100,
#     'verification_employee_code': 50,
#     'organisation_name': 150,
#     'organisation_code': 50,
#     'entity_type': 2,
#     'footer_record_count': 10,
#     'footer_fatca_record_count': 10,
#     'footer_additional_record_count': 10,
# }

# CKYC_MANDATORY_COLUMNS = frozenset({
#     'record_type',
#     'detail_record_type',
#     'detail_version',
#     'detail_flag',
# })


# def _ckycpk(col):
#     return models.BigAutoField(primary_key=True, db_column=col)


# def _ckycstr(col, **kw):
#     kw.setdefault('max_length', CKYC_COLUMN_MAX_LENGTHS[col])
#     db_column = kw.pop('db_column', col)
#     required = col in CKYC_MANDATORY_COLUMNS
#     if required:
#         kw.setdefault('default', '')
#     return models.CharField(
#         null=not required,
#         blank=not required,
#         db_column=db_column,
#         **kw,
#     )


# class Ckyc(models.Model):
#     """Editable CKYC file defaults used by the CKYC flat-file generator."""

#     id = _ckycpk('id')
#     locals().update({column: _ckycstr(column) for column in CKYC_COLUMN_MAX_LENGTHS})

#     class Meta:
#         db_table = 'ckyc'

#     def __str__(self):
#         return f'CKYC defaults {self.id}'


# class CkycStateCodeMaster(models.Model):
#     """Editable CKYC state-name to state-code mappings."""

#     id = models.BigAutoField(primary_key=True, db_column='id')
#     state_name = models.CharField(max_length=50, unique=True, db_column='state_name')
#     state_code = models.CharField(max_length=10, db_column='state_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'ckyc_state_code_master'
#         ordering = ('state_name',)

#     def __str__(self):
#         return f'{self.state_name} - {self.state_code}'


# KRA_COLUMN_MAX_LENGTHS = {
#     'APP_UPDTFLG': 3,
#     'APP_POS_CODE': 50,
#     'APP_KRA_CODE': 10,
#     'APP_TYPE': 2,
#     'APP_NO': 50,
#     'APP_DATE': 20,
#     'APP_PAN_NO': 10,
#     'APP_PAN_COPY': 1,
#     'APP_EXMT': 1,
#     'APP_EXMT_CAT': 20,
#     'APP_EXMT_ID_PROOF': 10,
#     'APP_IPV_FLAG': 2,
#     'APP_IPV_DATE': 20,
#     'APP_GEN': 1,
#     'APP_NAME': 150,
#     'APP_F_NAME': 100,
#     'APP_REGNO': 50,
#     'APP_DOB_INCORP': 20,
#     'APP_COMMENCE_DT': 20,
#     'APP_NATIONALITY': 10,
#     'APP_OTH_NATIONALITY': 50,
#     'APP_COMP_STATUS': 20,
#     'APP_OTH_COMP_STATUS': 50,
#     'APP_RES_STATUS': 5,
#     'APP_RES_STATUS_PROOF': 20,
#     'APP_UID_NO': 20,
#     'APP_COR_ADD1': 55,
#     'APP_COR_ADD2': 55,
#     'APP_COR_ADD3': 55,
#     'APP_COR_CITY': 50,
#     'APP_COR_PINCD': 10,
#     'APP_COR_STATE': 50,
#     'APP_COR_CTRY': 10,
#     'APP_OFF_ISD': 5,
#     'APP_OFF_STD': 5,
#     'APP_OFF_NO': 24,
#     'APP_RES_ISD': 5,
#     'APP_RES_STD': 5,
#     'APP_RES_NO': 24,
#     'APP_MOB_ISD': 5,
#     'APP_MOB_NO': 24,
#     'APP_FAX_ISD': 5,
#     'APP_FAX_STD': 5,
#     'APP_FAX_NO': 24,
#     'APP_EMAIL': 100,
#     'APP_COR_ADD_PROOF': 20,
#     'APP_COR_ADD_REF': 50,
#     'APP_COR_ADD_DT': 20,
#     'APP_PER_ADD_FLAG': 1,
#     'APP_PER_ADD1': 55,
#     'APP_PER_ADD2': 55,
#     'APP_PER_ADD3': 55,
#     'APP_PER_CITY': 50,
#     'APP_PER_PINCD': 10,
#     'APP_PER_STATE': 50,
#     'APP_PER_CTRY': 10,
#     'APP_PER_ADD_PROOF': 20,
#     'APP_PER_ADD_REF': 50,
#     'APP_PER_ADD_DT': 20,
#     'APP_INCOME': 50,
#     'APP_OCC': 50,
#     'APP_OTH_OCC': 50,
#     'APP_POL_CONN': 5,
#     'APP_DOC_PROOF': 20,
#     'APP_INTERNAL_REF': 50,
#     'APP_BRANCH_CODE': 50,
#     'APP_MAR_STATUS': 10,
#     'APP_NETWRTH': 30,
#     'APP_NETWORTH_DT': 20,
#     'APP_INCORP_PLC': 50,
#     'APP_OTHERINFO': 100,
#     'APP_FILLER1': 10,
#     'APP_FILLER2': 10,
#     'APP_FILLER3': 10,
#     'APP_IPV_NAME': 50,
#     'APP_IPV_DESG': 50,
#     'APP_IPV_ORGAN': 50,
#     'APP_KYC_MODE': 5,
#     'APP_VER_NO': 20,
#     'APP_VID_NO': 20,
#     'APP_UID_TOKEN': 50 ,
#     'APP_AUTH_NAME': 50,
#     'APP_AUTH_EMAIL': 50,
#     'APP_AUTH_EMAIL1': 50,
#     'APP_AUTH_EMAIL2': 50,
#     'APP_AUTH_MOBILE': 24,
#     'APP_AUTH_FPICONSENT': 1,
#     'APP_AUTH_UBOCONSENT': 1,
#     'APP_FATCA_APPLICABLE_FLAG': 1,
#     'APP_FATCA_BIRTH_PLACE': 50,
#     'APP_FATCA_BIRTH_COUNTRY': 10,
#     'APP_FATCA_COUNTRY_RES': 10,
#     'APP_FATCA_COUNTRY_CITYZENSHIP': 10,
#     'APP_FATCA_DATE_DECLARATION': 20,
#     'APP_MOBILE_FLG': 1,
#     'APP_EMAIL_FLG': 1,
#     'APP_OTP_REFNO': 50,
#     'APP_PERM_DISTRICT': 50,
#     'APP_CORR_DISTRICT': 50,
#     'COMPANY_CODE': 50,
#     'BATCH_DATE': 20,
#     'NO_OF_KYC_RECORDS': 10,
#     'APP_FATCADATA_RECORDS': 10,
#     'NO_OF_ADDLDATA_RECORDS': 10,
# }



# KRA_MANDATORY_COLUMNS = frozenset({
#     'APP_DATE',
#     'APP_KRA_CODE',
#     'APP_NAME',
#     'APP_PAN_NO',
#     'APP_POS_CODE',
#     'APP_UPDTFLG',
# })


# def _krapk(col):
#     return models.BigAutoField(primary_key=True, db_column=col)


# def _krastr(col, **kw):
#     kw.setdefault('max_length', KRA_COLUMN_MAX_LENGTHS[col])
#     db_column = kw.pop('db_column', col)
#     required = col in KRA_MANDATORY_COLUMNS
#     if required:
#         kw.setdefault('default', '')
#     field_class = models.TextField
#     return field_class(null=not required, blank=not required, db_column=db_column, **kw)


# class Kra(models.Model):
#     """Editable static/default fields for the CVL KRA payload."""

#     id = _krapk('id')
#     locals().update({column: _krastr(column) for column in KRA_COLUMN_MAX_LENGTHS})

#     class Meta:
#         db_table = 'kra'

#     def __str__(self):
#         return f'KRA defaults {self.id}'


# class KraStatusMaster(models.Model):
#     """Editable KRA APP status to update/provider mapping."""

#     id = models.BigAutoField(primary_key=True, db_column='id')
#     app_status = models.CharField(max_length=3, unique=True, db_column='app_status')
#     update_flag = models.CharField(max_length=3, db_column='update_flag')
#     kra_code = models.CharField(max_length=6, db_column='kra_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'kra_status_master'
#         ordering = ('id',)

#     def __str__(self):
#         return f'{self.app_status} - {self.update_flag} - {self.kra_code}'


# class KraErrorCode(models.Model):
#     """Editable CVL KRA provider error-code messages."""

#     code = models.CharField(max_length=10, unique=True, db_column='code')
#     message = models.CharField(max_length=112, db_column='message')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'kra_error_code'
#         ordering = ('code',)

#     def __str__(self):
#         return f'{self.code} - {self.message}'


# class KraMaritalStatusMaster(models.Model):
#     """Editable KRA marital-status mappings."""

#     id = models.BigAutoField(primary_key=True, db_column='id')
#     marital_status = models.CharField(max_length=50, unique=True, db_column='marital_status')
#     marital_code = models.CharField(max_length=10, db_column='marital_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'kra_marital_status_master'
#         ordering = ('marital_status',)

#     def __str__(self):
#         return f'{self.marital_status} - {self.marital_code}'


# class KraGenderMaster(models.Model):
#     """Editable KRA gender mappings."""

#     id = models.BigAutoField(primary_key=True, db_column='id')
#     gender = models.CharField(max_length=50, unique=True, db_column='gender')
#     gender_code = models.CharField(max_length=10, db_column='gender_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'kra_gender_master'
#         ordering = ('gender',)

#     def __str__(self):
#         return f'{self.gender} - {self.gender_code}'

# class KraCredentials(models.Model):
#     """CVL KRA credentials for one company and environment."""

#     id = models.BigAutoField(primary_key=True, db_column='id')
#     user = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name='kra_credentials',
#         db_column='user_id',
#     )
#     environment = models.CharField(max_length=10, default='uat')
#     token_url = models.TextField(max_length=255, blank=True, default='')
#     pan_status_url = models.TextField(max_length=255, blank=True, default='')
#     fetch_data_url = models.TextField(max_length=255, blank=True, default='')
#     insert_data_url = models.TextField(max_length=255, blank=True, default='')
#     api_key = models.TextField(max_length=255, blank=True, default='')
#     username = models.CharField(max_length=100, blank=True, default='')
#     poscode = models.CharField(max_length=50, blank=True, default='')
#     cvlkra_password = models.CharField(max_length=100, blank=True, default='')
#     aes_key = models.TextField(max_length=255, blank=True, default='')
#     # Optional CVL KRA SFTP credentials used for PDF/XML document upload.
#     sftp_host = models.CharField(max_length=100, blank=True, default='')
#     sftp_port = models.CharField(max_length=10, blank=True, default='22')
#     sftp_username = models.CharField(max_length=100, blank=True, default='')
#     sftp_password = models.CharField(max_length=100, blank=True, default='')
#     sftp_base_path = models.CharField(max_length=100, blank=True, default='.')
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'kra_credentials'
#         unique_together = (('user', 'environment'),)

#     def __str__(self):
#         return f'{self.user_id or self.id} - {self.environment}'

# class CkycCredentials(models.Model):
#     """CKYC credentials for one company and environment."""

#     id = models.BigAutoField(primary_key=True, db_column='id')
#     user = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name='ckyc_credentials',
#         db_column='user_id',
#     )
#     environment = models.CharField(max_length=10, default='uat')
#     ckyc_base_url = models.TextField(max_length=255, blank=True, default='')
#     auth_api_key = models.TextField(max_length=255, blank=True, default='')
#     username = models.CharField(max_length=100, blank=True, default='')
#     password = models.CharField(max_length=100, blank=True, default='')
#     ficode_ckyc = models.CharField(max_length=50, blank=True, default='')
#     region_or_branch_code_ckyc = models.CharField(max_length=50, blank=True, default='')
#     userid_ckyc = models.CharField(max_length=50, blank=True, default='')
#     KYCVerificationName = models.CharField(max_length=100, blank=True, default='')
#     KYCVerificationDesignation = models.CharField(max_length=100, blank=True, default='')
#     KYCVerificationBranch = models.CharField(max_length=100, blank=True, default='')
#     KYCVerificationEMPcode = models.CharField(max_length=50, blank=True, default='')
#     OrganisationName = models.CharField(max_length=150, blank=True, default='')
#     OrganisationCode = models.CharField(max_length=50, blank=True, default='')
#     # Optional encrypted CKYC search/download endpoints and signing keys.
#     # The flat-file push flow continues to use the fields above.
#     verify_url = models.TextField(max_length=500, blank=True, default='')
#     download_url = models.TextField(max_length=255, blank=True, default='')
#     verify_otp_url = models.TextField(max_length=255, blank=True, default='')
#     fi_private_key_path = models.TextField(max_length=255, blank=True, default='')
#     fi_public_key_path = models.TextField(max_length=255, blank=True, default='')
#     cersai_public_key_path = models.TextField(max_length=255, blank=True, default='')
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'ckyc_credentials'
#         unique_together = (('user', 'environment'),)

#     def __str__(self):
#         return f'{self.user_id or self.id} - {self.environment}'


# class CkycTransaction(models.Model):
#     """State for encrypted CKYC verify/download/OTP requests."""

#     id = models.BigAutoField(primary_key=True, db_column='id')
#     client = models.ForeignKey(
#         UserDetails,
#         on_delete=models.CASCADE,
#         related_name='ckyc_transactions',
#         db_column='client_id',
#     )
#     environment = models.CharField(max_length=10, default='uat')
#     pan = models.CharField(max_length=50, blank=True, default='')
#     reference_id = models.CharField(max_length=50, blank=True, default='')
#     request_id = models.CharField(max_length=50, blank=True, default='')
#     auth_factor = models.CharField(max_length=50, blank=True, default='')
#     status = models.CharField(max_length=30, blank=True, default='')
#     response_data = models.TextField(blank=True, default='')
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'ckyc_transactions'
#         ordering = ('-id',)

#     def __str__(self):
#         return f'{self.client_id} - {self.reference_id or self.request_id or self.id}'


# def _credentialnsestr(col, **kw):
#     kw.setdefault('max_length', 50)
#     db_column = kw.pop('db_column', col)
#     return models.CharField(null=True, blank=True, db_column=db_column, **kw)

# class NseCredentials(models.Model):
#     id = models.BigAutoField(primary_key=True, db_column='id')
#     user = models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.CASCADE,db_column='user_id',related_name='nse_credentials')
#     username = _credentialnsestr('username')
#     password = _credentialnsestr('password')
#     apiName = _credentialnsestr('apiName')
#     created_at = models.DateTimeField(auto_now_add=True,db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True,db_column='updated_at')

#     class Meta:
#         db_table = 'nse_credentials'
#         unique_together = (('user',),)

#     def __str__(self):
#         return f"{self.user_id or self.id}"


# class MseCredentials(models.Model):
#     """MSE India UCC API credentials for one company user."""

#     user = models.OneToOneField(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name='mse_credentials',
#         db_column='user_id',
#     )
#     environment = models.CharField(max_length=10, default='uat')
#     login_id = models.CharField(max_length=50, blank=True, default='')
#     password = models.CharField(max_length=50, blank=True, default='')
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'mse_credentials'

#     def __str__(self):
#         return f'{self.user_id or self.id} - {self.environment}'


# class NseStateCodeMaster(models.Model):
#     id = models.BigAutoField(primary_key=True, db_column='id')
#     state_name = models.CharField(max_length=50, unique=True, db_column='state_name')
#     state_code = models.CharField(max_length=50, db_column='state_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'nse_state_code_master'
#         ordering = ('state_name',)

#     def __str__(self):
#         return f"{self.state_name} - {self.state_code}"


# class NseMaritalStatusMaster(models.Model):
#     id = models.BigAutoField(primary_key=True, db_column='id')
#     marital_status = models.CharField(max_length=50, unique=True, db_column='marital_status')
#     marital_code = models.CharField(max_length=50, db_column='marital_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'nse_marital_status_master'
#         ordering = ('marital_status',)

#     def __str__(self):
#         return f"{self.marital_status} - {self.marital_code}"


# class NseOccupationMaster(models.Model):
#     id = models.BigAutoField(primary_key=True, db_column='id')
#     occupation_name = models.CharField(max_length=50, unique=True, db_column='occupation_name')
#     occupation_code = models.CharField(max_length=50, db_column='occupation_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'nse_occupation_master'
#         ordering = ('occupation_name',)

#     def __str__(self):
#         return f"{self.occupation_name} - {self.occupation_code}"


# class NseIncomeRangeMaster(models.Model):
#     id = models.BigAutoField(primary_key=True, db_column='id')
#     income_range = models.CharField(max_length=50, unique=True, db_column='income_range')
#     income_code = models.CharField(max_length=50, db_column='income_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'nse_income_range_master'
#         ordering = ('id',)

#     def __str__(self):
#         return f"{self.income_range} - {self.income_code}"


# class BseIncomeRangeMaster(models.Model):
#     id = models.BigAutoField(primary_key=True, db_column='id')
#     income_range = models.CharField(max_length=50, unique=True, db_column='income_range')
#     income_code = models.CharField(max_length=50, db_column='income_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'bse_income_range_master'
#         ordering = ('id',)

#     def __str__(self):
#         return f"{self.income_range} - {self.income_code}"


# CDSL_COLUMN_MAX_LENGTHS = {
#     'CntrlSctiesDpstryPtcpt': 8,
#     'BrnchId': 6,
#     'BtchId': 8,
#     'SndrId': 8,
#     'CntrlSctiesDpstryPtcptRole': 3,
#     'SndrDt': 30,
#     'RcvDt': 30,
#     'RcrdNb': 6,
#     'RcdSRNumber': 7,
#     'BOTxnTyp': 5,
#     'ClntId': 16,
#     'PrdNb': 5,
#     'BnfcrySubTp': 7,
#     'Purpse': 7,
#     'Titl': 10,
#     'FrstNm': 135,
#     'MddlNm': 20,
#     'LastNm': 20,
#     'FSfx': 10,
#     'BnfcryShrtNm': 16,
#     'ScndHldrNmOfFthr': 50,
#     'BirthDt': 30,
#     'Gndr': 5,
#     'PAN': 10,
#     'PANVrfyFlg': 6,
#     'PANXmptnCd': 6,
#     'UID': 16,
#     'AdhrAuthntcnWthUID': 5,
#     'RsnForNonUpdtdAdhr': 6,
#     'VID': 16,
#     'SMSFclty': 3,
#     'PrmryISDCd': 6,
#     'MobNb': 24,
#     'FmlyFlgForMobNbOf': 3,
#     'ScndryISDCd': 6,
#     'PhneNb': 24,
#     'EmailAdr': 100,
#     'FmlyFlgForEmailAdr': 3,
#     'AltrnEmailAdr': 100,
#     'NoNmntnFlg': 3,
#     'MdOfOpr': 6,
#     'ClrMmbId': 16,
#     'StgInstr': 3,
#     'GrssAnlIncmRg': 6,
#     'NetWrth': 18,
#     'NetWrthAsOnDt': 30,
#     'LEI': 20,
#     'LEIExp': 30,
#     'OneTmDclrtnFlgForGSECIDT': 6,
#     'INIFSC': 15,
#     'MICRCd': 12,
#     'DvddCcy': 6,
#     'DvddBkCcy': 6,
#     'RBIApprvdDt': 30,
#     'RBIRefNb': 50,
#     'Mndt': 3,
#     'SEBIRegNb': 24,
#     'EdctnLvl': 4,
#     'AnlRptFlg': 3,
#     'BnfclOwnrSttlmCyclCd': 2,
#     'ElctrncConf': 3,
#     'EmailRTADwnldFlg': 3,
#     'GeoCd': 5,
#     'Xchg': 3,
#     'MntlDsblty': 3,
#     'Ntlty': 5,
#     'CASMd': 2,
#     'AncstrlFlg': 3,
#     'PldgStgInstrFlg': 3,
#     'BkAcctTp': 3,
#     'BnfcryAcctCtgy': 3,
#     'BnfcryBkAcctNb': 30,
#     'BnfcryBkNm': 135,
#     'BnfcryTaxDdctnSts': 5,
#     'ClrSysId': 6,
#     'BSDAFlg': 4,
#     'Ocptn': 4,
#     'PMSClntAcctFlg': 4,
#     'PMSSEBIRegnNb': 12,
#     'PostvConf': 3,
#     'FrstClntOptnToRcvElctrncStmtFlg': 3,
#     'ComToBeSentTo': 3,
#     'DelFlg': 4,
#     'RsnCdDeltn': 3,
#     'DtOfDeath': 30,
#     'AccntOpSrc': 6,
#     'CustdPmsEmailId': 50,
#     'POAOrDDPITp': 5,
#     'TradgId': 8,
#     'SndrRefNb1': 35,
#     'SndrRefNb2': 35,
#     'CtdnFlg': 3,
#     'DmtrlstnGtwy': 3,
#     'NmneeMnrInd': 3,
#     'SrlNbr': 2,
#     'NmneePctgOfShr': 3,
#     'FlgForShrPctgEqlty': 3,
#     'RsdlSecFlg': 3,
#     'RltshWthBnfclOwnr': 3,
#     'NbOfPOAMppng': 5,
#     'POAId': 16,
#     'POAToOprtAcct': 3,
#     'POAOrDDPIId': 16,
#     'SetUpDt': 30,
#     'FrDt': 30,
#     'ToDt': 30,
#     'GPABPAFlg': 3,
#     'POAMstrID': 16,
#     'PoaLnkPurpCd': 3,
#     'Rmk': 100,
#     'BOUCCLkFlg': 3,
#     'CnsntInd': 6,
#     'UnqClntId': 11,
#     'Brkr': 8,
#     'Sgmt': 2,
#     'MapUMapFlg': 3,
#     'CmAcctToMap': 16,
#     'PurpCd': 5,
#     'AdrPrefFlg': 3,
#     'Adr1': 55,
#     'Adr2': 55,
#     'Adr3': 55,
#     'Adr4': 36,
#     'Ctry': 5,
#     'PstCd': 10,
#     'CtrySubDvsnCd': 3,
#     'CitySeqNb': 2,
#     'FaxNb': 24,
#     'ITCrcl': 15,
#     'ProofOfRes': 3,
#     'NbOfCoprcnrs': 2,
#     'SgntryId': 9,
#     'SgntrSz': 5,
#     'BnfclOwnrAcctOfPMSFlg': 3,
#     'CrspdngBPId': 8,
#     'ClngMbrPAN': 30,
#     'LclAddPrsnt': 3,
#     'BnkAddPrsnt': 3,
#     'NmnorGrdnAddPrsnt': 3,
#     'MnrNmnGrdnAddPrsnt': 3,
#     'FrgnOrCorrAddPrsnt': 3,
#     'NbOfAuthSgnt': 9,
#     'AuthFlg': 3,
#     'CoprcnrOrMmbr': 3,
#     'TypMod': 5,
#     'SubTypMod': 7,
#     'StsChgRsnOrClsrRsnCd': 6,
#     'NmChgRsnCd': 6,
#     'ExecDt': 30,
#     'AddModDelInd': 3,
#     'AppKrta': 3,
#     'ChgKrtaRsn': 5,
#     'DtIntmnBO': 30,
#     'PrfDpstryFldFrCAS': 4,
#     'CoprcnrsId': 2,
#     'ClsrInitBy': 2,
#     'RmngBal': 3,
#     'CANm': 135,
#     'CertNbr': 50,
#     'CertXpryDt': 30,
#     'NbrPOASgntryReqSign': 4,
#     'DpstryInd': 4,
#     'AcctTyp': 3,
#     'SrcCMBPID': 8,
#     'TrgtDPID': 8,
#     'TrgtClntID': 16,
#     'SrlFlg': 3,
#     'UPIId': 100,
#     'SignTyp': 3,
#     'NBOID': 16,
#     'ClntBsdaOptOutDt': 30,
#     'CtrySubDvsnNm': 50,
#     'RsnBSDAMod': 50,
#     'DtIntmnDms': 30,
#     'Drl': 20,
#     'Psprt': 20,
#     'NmStmtFlg': 3,
#     'RsnDlayClsReq': 100,
#     'SpPurpFlg': 3,
#     'CnsntMode': 3,
#     'DrpanId': 50,
#     'Rsvd1': 50,
#     'Rsvd2': 50,
#     'Rsvd3': 50,
#     'Rsvd4': 50,
# }

# CDSL_MANDATORY_COLUMNS = {
#     'CntrlSctiesDpstryPtcpt',
#     'BtchId',
#     'SndrId',
#     'SndrDt',
#     'RcvDt',
#     'RcrdNb',
#     'RcdSRNumber',
#     'BOTxnTyp',
#     'ClntId',
#     'PrdNb',
#     'BnfcrySubTp',
#     'Purpse',
#     'Titl',
#     'FrstNm',
#     'LastNm',
#     'BnfcryShrtNm',
#     'ScndHldrNmOfFthr',
#     'BirthDt',
#     'Gndr',
#     'PAN',
#     'PANVrfyFlg',
#     'UID',
#     'AdhrAuthntcnWthUID',
#     'SMSFclty',
#     'PrmryISDCd',
#     'MobNb',
#     'FmlyFlgForMobNbOf',
#     'EmailAdr',
#     'FmlyFlgForEmailAdr',
#     'MdOfOpr',
#     'StgInstr',
#     'GrssAnlIncmRg',
#     'INIFSC',
#     'MICRCd',
#     'DvddCcy',
#     'DvddBkCcy',
#     'Mndt',
#     'EdctnLvl',
#     'AnlRptFlg',
#     'BnfclOwnrSttlmCyclCd',
#     'Ntlty',
#     'AncstrlFlg',
#     'PldgStgInstrFlg',
#     'BkAcctTp',
#     'BnfcryAcctCtgy',
#     'BnfcryBkAcctNb',
#     'BnfcryBkNm',
#     'BnfcryTaxDdctnSts',
#     'ClrSysId',
#     'BSDAFlg',
#     'Ocptn',
#     'PMSClntAcctFlg',
#     'FrstClntOptnToRcvElctrncStmtFlg',
#     'ComToBeSentTo',
#     'AccntOpSrc',
#     'SndrRefNb1',
#     'CtdnFlg',
#     'NmneeMnrInd',
#     'POAToOprtAcct',
#     'UnqClntId',
#     'PurpCd',
#     'AdrPrefFlg',
#     'Adr1',
#     'Adr2',
#     'Adr3',
#     'Adr4',
#     'Ctry',
#     'PstCd',
#     'CtrySubDvsnCd',
#     'CitySeqNb',
#     'BnfclOwnrAcctOfPMSFlg',
#     'LclAddPrsnt',
#     'BnkAddPrsnt',
#     'NmnorGrdnAddPrsnt',
#     'MnrNmnGrdnAddPrsnt',
#     'FrgnOrCorrAddPrsnt',
#     'SrlFlg',
# }

# def _cdslpk(col):
#     return models.BigAutoField(primary_key=True, db_column=col)

# def _cdslstr(col, **kw):
#     kw.setdefault('max_length', CDSL_COLUMN_MAX_LENGTHS[col])
#     db_column = kw.pop('db_column', col)
#     required = col in CDSL_MANDATORY_COLUMNS
#     if required:
#         kw.setdefault('default', '')
#         kw.setdefault('db_default', '')
#     return models.TextField(null=not required,blank=not required,db_column=db_column,**kw)

# class Cdsl(models.Model):
#     """Configurable default values for CDSL BO opening and modification files."""
#     id = _cdslpk('id')
#     CntrlSctiesDpstryPtcpt = _cdslstr('CntrlSctiesDpstryPtcpt')
#     BrnchId = _cdslstr('BrnchId')
#     BtchId = _cdslstr('BtchId')
#     SndrId = _cdslstr('SndrId')
#     CntrlSctiesDpstryPtcptRole = _cdslstr('CntrlSctiesDpstryPtcptRole')
#     SndrDt = _cdslstr('SndrDt')
#     RcvDt = _cdslstr('RcvDt')
#     RcrdNb = _cdslstr('RcrdNb')
#     RcdSRNumber = _cdslstr('RcdSRNumber')
#     BOTxnTyp = _cdslstr('BOTxnTyp')
#     ClntId = _cdslstr('ClntId')
#     PrdNb = _cdslstr('PrdNb')
#     BnfcrySubTp = _cdslstr('BnfcrySubTp')
#     Purpse = _cdslstr('Purpse')
#     Titl = _cdslstr('Titl')
#     FrstNm = _cdslstr('FrstNm')
#     MddlNm = _cdslstr('MddlNm')
#     LastNm = _cdslstr('LastNm')
#     FSfx = _cdslstr('FSfx')
#     BnfcryShrtNm = _cdslstr('BnfcryShrtNm')
#     ScndHldrNmOfFthr = _cdslstr('ScndHldrNmOfFthr')
#     BirthDt = _cdslstr('BirthDt')
#     Gndr = _cdslstr('Gndr')
#     PAN = _cdslstr('PAN')
#     PANVrfyFlg = _cdslstr('PANVrfyFlg')
#     PANXmptnCd = _cdslstr('PANXmptnCd')
#     UID = _cdslstr('UID')
#     AdhrAuthntcnWthUID = _cdslstr('AdhrAuthntcnWthUID')
#     RsnForNonUpdtdAdhr = _cdslstr('RsnForNonUpdtdAdhr')
#     VID = _cdslstr('VID')
#     SMSFclty = _cdslstr('SMSFclty')
#     PrmryISDCd = _cdslstr('PrmryISDCd')
#     MobNb = _cdslstr('MobNb')
#     FmlyFlgForMobNbOf = _cdslstr('FmlyFlgForMobNbOf')
#     ScndryISDCd = _cdslstr('ScndryISDCd')
#     PhneNb = _cdslstr('PhneNb')
#     EmailAdr = _cdslstr('EmailAdr')
#     FmlyFlgForEmailAdr = _cdslstr('FmlyFlgForEmailAdr')
#     AltrnEmailAdr = _cdslstr('AltrnEmailAdr')
#     NoNmntnFlg = _cdslstr('NoNmntnFlg')
#     MdOfOpr = _cdslstr('MdOfOpr')
#     ClrMmbId = _cdslstr('ClrMmbId')
#     StgInstr = _cdslstr('StgInstr')
#     GrssAnlIncmRg = _cdslstr('GrssAnlIncmRg')
#     NetWrth = _cdslstr('NetWrth')
#     NetWrthAsOnDt = _cdslstr('NetWrthAsOnDt')
#     LEI = _cdslstr('LEI')
#     LEIExp = _cdslstr('LEIExp')
#     OneTmDclrtnFlgForGSECIDT = _cdslstr('OneTmDclrtnFlgForGSECIDT')
#     INIFSC = _cdslstr('INIFSC')
#     MICRCd = _cdslstr('MICRCd')
#     DvddCcy = _cdslstr('DvddCcy')
#     DvddBkCcy = _cdslstr('DvddBkCcy')
#     RBIApprvdDt = _cdslstr('RBIApprvdDt')
#     RBIRefNb = _cdslstr('RBIRefNb')
#     Mndt = _cdslstr('Mndt')
#     SEBIRegNb = _cdslstr('SEBIRegNb')
#     EdctnLvl = _cdslstr('EdctnLvl')
#     AnlRptFlg = _cdslstr('AnlRptFlg')
#     BnfclOwnrSttlmCyclCd = _cdslstr('BnfclOwnrSttlmCyclCd')
#     ElctrncConf = _cdslstr('ElctrncConf')
#     EmailRTADwnldFlg = _cdslstr('EmailRTADwnldFlg')
#     GeoCd = _cdslstr('GeoCd')
#     Xchg = _cdslstr('Xchg')
#     MntlDsblty = _cdslstr('MntlDsblty')
#     Ntlty = _cdslstr('Ntlty')
#     CASMd = _cdslstr('CASMd')
#     AncstrlFlg = _cdslstr('AncstrlFlg')
#     PldgStgInstrFlg = _cdslstr('PldgStgInstrFlg')
#     BkAcctTp = _cdslstr('BkAcctTp')
#     BnfcryAcctCtgy = _cdslstr('BnfcryAcctCtgy')
#     BnfcryBkAcctNb = _cdslstr('BnfcryBkAcctNb')
#     BnfcryBkNm = _cdslstr('BnfcryBkNm')
#     BnfcryTaxDdctnSts = _cdslstr('BnfcryTaxDdctnSts')
#     ClrSysId = _cdslstr('ClrSysId')
#     BSDAFlg = _cdslstr('BSDAFlg')
#     Ocptn = _cdslstr('Ocptn')
#     PMSClntAcctFlg = _cdslstr('PMSClntAcctFlg')
#     PMSSEBIRegnNb = _cdslstr('PMSSEBIRegnNb')
#     PostvConf = _cdslstr('PostvConf')
#     FrstClntOptnToRcvElctrncStmtFlg = _cdslstr('FrstClntOptnToRcvElctrncStmtFlg')
#     ComToBeSentTo = _cdslstr('ComToBeSentTo')
#     DelFlg = _cdslstr('DelFlg')
#     RsnCdDeltn = _cdslstr('RsnCdDeltn')
#     DtOfDeath = _cdslstr('DtOfDeath')
#     AccntOpSrc = _cdslstr('AccntOpSrc')
#     CustdPmsEmailId = _cdslstr('CustdPmsEmailId')
#     POAOrDDPITp = _cdslstr('POAOrDDPITp')
#     TradgId = _cdslstr('TradgId')
#     SndrRefNb1 = _cdslstr('SndrRefNb1')
#     SndrRefNb2 = _cdslstr('SndrRefNb2')
#     CtdnFlg = _cdslstr('CtdnFlg')
#     DmtrlstnGtwy = _cdslstr('DmtrlstnGtwy')
#     NmneeMnrInd = _cdslstr('NmneeMnrInd')
#     SrlNbr = _cdslstr('SrlNbr')
#     NmneePctgOfShr = _cdslstr('NmneePctgOfShr')
#     FlgForShrPctgEqlty = _cdslstr('FlgForShrPctgEqlty')
#     RsdlSecFlg = _cdslstr('RsdlSecFlg')
#     RltshWthBnfclOwnr = _cdslstr('RltshWthBnfclOwnr')
#     NbOfPOAMppng = _cdslstr('NbOfPOAMppng')
#     POAId = _cdslstr('POAId')
#     POAToOprtAcct = _cdslstr('POAToOprtAcct')
#     POAOrDDPIId = _cdslstr('POAOrDDPIId')
#     SetUpDt = _cdslstr('SetUpDt')
#     FrDt = _cdslstr('FrDt')
#     ToDt = _cdslstr('ToDt')
#     GPABPAFlg = _cdslstr('GPABPAFlg')
#     POAMstrID = _cdslstr('POAMstrID')
#     PoaLnkPurpCd = _cdslstr('PoaLnkPurpCd')
#     Rmk = _cdslstr('Rmk')
#     BOUCCLkFlg = _cdslstr('BOUCCLkFlg')
#     CnsntInd = _cdslstr('CnsntInd')
#     UnqClntId = _cdslstr('UnqClntId')
#     Brkr = _cdslstr('Brkr')
#     Sgmt = _cdslstr('Sgmt')
#     MapUMapFlg = _cdslstr('MapUMapFlg')
#     CmAcctToMap = _cdslstr('CmAcctToMap')
#     PurpCd = _cdslstr('PurpCd')
#     AdrPrefFlg = _cdslstr('AdrPrefFlg')
#     Adr1 = _cdslstr('Adr1')
#     Adr2 = _cdslstr('Adr2')
#     Adr3 = _cdslstr('Adr3')
#     Adr4 = _cdslstr('Adr4')
#     Ctry = _cdslstr('Ctry')
#     PstCd = _cdslstr('PstCd')
#     CtrySubDvsnCd = _cdslstr('CtrySubDvsnCd')
#     CitySeqNb = _cdslstr('CitySeqNb')
#     FaxNb = _cdslstr('FaxNb')
#     ITCrcl = _cdslstr('ITCrcl')
#     ProofOfRes = _cdslstr('ProofOfRes')
#     NbOfCoprcnrs = _cdslstr('NbOfCoprcnrs')
#     SgntryId = _cdslstr('SgntryId')
#     SgntrSz = _cdslstr('SgntrSz')
#     BnfclOwnrAcctOfPMSFlg = _cdslstr('BnfclOwnrAcctOfPMSFlg')
#     CrspdngBPId = _cdslstr('CrspdngBPId')
#     ClngMbrPAN = _cdslstr('ClngMbrPAN')
#     LclAddPrsnt = _cdslstr('LclAddPrsnt')
#     BnkAddPrsnt = _cdslstr('BnkAddPrsnt')
#     NmnorGrdnAddPrsnt = _cdslstr('NmnorGrdnAddPrsnt')
#     MnrNmnGrdnAddPrsnt = _cdslstr('MnrNmnGrdnAddPrsnt')
#     FrgnOrCorrAddPrsnt = _cdslstr('FrgnOrCorrAddPrsnt')
#     NbOfAuthSgnt = _cdslstr('NbOfAuthSgnt')
#     AuthFlg = _cdslstr('AuthFlg')
#     CoprcnrOrMmbr = _cdslstr('CoprcnrOrMmbr')
#     TypMod = _cdslstr('TypMod')
#     SubTypMod = _cdslstr('SubTypMod')
#     StsChgRsnOrClsrRsnCd = _cdslstr('StsChgRsnOrClsrRsnCd')
#     NmChgRsnCd = _cdslstr('NmChgRsnCd')
#     ExecDt = _cdslstr('ExecDt')
#     AddModDelInd = _cdslstr('AddModDelInd')
#     AppKrta = _cdslstr('AppKrta')
#     ChgKrtaRsn = _cdslstr('ChgKrtaRsn')
#     DtIntmnBO = _cdslstr('DtIntmnBO')
#     PrfDpstryFldFrCAS = _cdslstr('PrfDpstryFldFrCAS')
#     CoprcnrsId = _cdslstr('CoprcnrsId')
#     ClsrInitBy = _cdslstr('ClsrInitBy')
#     RmngBal = _cdslstr('RmngBal')
#     CANm = _cdslstr('CANm')
#     CertNbr = _cdslstr('CertNbr')
#     CertXpryDt = _cdslstr('CertXpryDt')
#     NbrPOASgntryReqSign = _cdslstr('NbrPOASgntryReqSign')
#     DpstryInd = _cdslstr('DpstryInd')
#     AcctTyp = _cdslstr('AcctTyp')
#     SrcCMBPID = _cdslstr('SrcCMBPID')
#     TrgtDPID = _cdslstr('TrgtDPID')
#     TrgtClntID = _cdslstr('TrgtClntID')
#     SrlFlg = _cdslstr('SrlFlg')
#     UPIId = _cdslstr('UPIId')
#     SignTyp = _cdslstr('SignTyp')
#     NBOID = _cdslstr('NBOID')
#     ClntBsdaOptOutDt = _cdslstr('ClntBsdaOptOutDt')
#     CtrySubDvsnNm = _cdslstr('CtrySubDvsnNm')
#     RsnBSDAMod = _cdslstr('RsnBSDAMod')
#     DtIntmnDms = _cdslstr('DtIntmnDms')
#     Drl = _cdslstr('Drl')
#     Psprt = _cdslstr('Psprt')
#     NmStmtFlg = _cdslstr('NmStmtFlg')
#     RsnDlayClsReq = _cdslstr('RsnDlayClsReq')
#     SpPurpFlg = _cdslstr('SpPurpFlg')
#     CnsntMode = _cdslstr('CnsntMode')
#     DrpanId = _cdslstr('DrpanId')
#     Rsvd1 = _cdslstr('Rsvd1')
#     Rsvd2 = _cdslstr('Rsvd2')
#     Rsvd3 = _cdslstr('Rsvd3')
#     Rsvd4 = _cdslstr('Rsvd4')

#     class Meta:
#         db_table = "cdsl"


# class CdslCredentials(models.Model):
#     user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
#     DPID = models.CharField(max_length=8)
#     UserID = models.CharField(max_length=50)
#     Password = models.CharField(max_length=255)
#     AES_key = models.CharField(max_length=32)
#     last_batch = models.PositiveIntegerField(default=0, editable=False)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'cdsl_credentials'


# MCX_MANDATORY_COLUMNS = frozenset({
#     'record_type',
#     'member_type',
#     'client_code',
#     'client_name',
#     'category',
#     'pan',
#     'gender',
#     'fathers_husbands_guardians_name',
#     'marital_status',
#     'nationality',
#     'client_email_id',
#     'address_1_corresponding',
#     'pin_code_corresponding',
#     'permanent_address_same_as_corresponding_address',
#     'mobile_number',
#     'date_of_birth_incorporation',
#     'bank_name_1',
#     'bank_branch_address_1',
#     'bank_account_number_1',
#     'bank_account_type_1',
#     'occupation',
#     'politically_exposed_person',
#     'in_person_verification',
#     'client_status',
#     'client_type_corporate',
#     'relationship_with_client_for_mobile_no',
#     'relationship_with_client_for_email_id',
#     'flag',
# })

# MCX_COLUMN_MAX_LENGTHS = {
#     column: 255
#     for column in MCX_MANDATORY_COLUMNS
# }
# MCX_COLUMN_MAX_LENGTHS.update({
#     'record_type': 10,
#     'member_type': 10,
#     'category': 10,
#     'client_code': 10,
#     'client_name': 150,
#     'pan': 10,
#     'gender': 2,
#     'fathers_husbands_guardians_name': 75,
#     'marital_status': 2,
#     'nationality': 2,
#     'client_email_id': 60,
#     'address_1_corresponding': 225,
#     'permanent_address_same_as_corresponding_address': 10,
#     'mobile_number': 24,
#     'pin_code_corresponding': 10,
#     'date_of_birth_incorporation': 8,
#     'bank_name_1': 60,
#     'bank_account_number_1': 25,
#     'bank_account_type_1': 2,
#     'occupation': 2,
#     'politically_exposed_person': 1,
#     'in_person_verification': 1,
#     'client_status': 1,
#     'client_type_corporate': 1,
#     'relationship_with_client_for_mobile_no': 10,
#     'relationship_with_client_for_email_id': 10,
#     'flag': 1,
# })


# def _mcxpk(col):
#     return models.BigAutoField(primary_key=True, db_column=col)


# def _mcxstr(col, **kw):
#     kw.setdefault('max_length', MCX_COLUMN_MAX_LENGTHS[col])
#     db_column = kw.pop('db_column', col)
#     required = col in MCX_MANDATORY_COLUMNS
#     if required:
#         kw.setdefault('default', '')
#     return models.CharField(
#         null=not required,
#         blank=not required,
#         db_column=db_column,
#         **kw,
#     )


# class Mcx(models.Model):
#     """Editable MCX KYC defaults and category-01 payload columns."""

#     id = _mcxpk('id')

#     # Top-level MCX control values.
#     record_type = _mcxstr('record_type', default='10')
#     member_type = _mcxstr('member_type', default='M')

#     # Category-01 fields. Dynamic values are overwritten from UserDetails
#     # while static values remain editable from the MCX master screen.
#     client_code = _mcxstr('client_code')
#     client_name = _mcxstr('client_name')
#     category = _mcxstr('category', default='01')
#     pan = _mcxstr('pan')
#     gender = _mcxstr('gender')
#     fathers_husbands_guardians_name = _mcxstr('fathers_husbands_guardians_name')
#     marital_status = _mcxstr('marital_status')
#     nationality = _mcxstr('nationality', default='1')
#     client_email_id = _mcxstr('client_email_id')
#     address_1_corresponding = _mcxstr('address_1_corresponding')
#     pin_code_corresponding = _mcxstr('pin_code_corresponding')
#     permanent_address_same_as_corresponding_address = _mcxstr(
#         'permanent_address_same_as_corresponding_address',
#         default='Y',
#     )
#     mobile_number = _mcxstr('mobile_number')
#     date_of_birth_incorporation = _mcxstr('date_of_birth_incorporation')
#     bank_name_1 = _mcxstr('bank_name_1')
#     bank_branch_address_1 = _mcxstr('bank_branch_address_1')
#     bank_account_number_1 = _mcxstr('bank_account_number_1')
#     bank_account_type_1 = _mcxstr('bank_account_type_1')
#     occupation = _mcxstr('occupation')
#     politically_exposed_person = _mcxstr('politically_exposed_person', default='0')
#     in_person_verification = _mcxstr('in_person_verification', default='Y')
#     client_status = _mcxstr('client_status', default='1')
#     client_type_corporate = _mcxstr('client_type_corporate', default='N')
#     relationship_with_client_for_mobile_no = _mcxstr(
#         'relationship_with_client_for_mobile_no',
#         default='1',
#     )
#     relationship_with_client_for_email_id = _mcxstr(
#         'relationship_with_client_for_email_id',
#         default='1',
#     )
#     flag = _mcxstr('flag', default='E')

#     class Meta:
#         db_table = 'mcx'


# class McxCredentials(models.Model):
#     """MCX credentials for one company user."""

#     user = models.OneToOneField(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name='mcx_credentials',
#         db_column='user_id',
#     )
#     environment = models.CharField(max_length=10, default='uat')
#     member_id = models.CharField(max_length=50, blank=True, default='')
#     api_key = models.CharField(max_length=255, blank=True, default='')
#     aes_key = models.CharField(max_length=64, blank=True, default='')
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'mcx_credentials'


# class McxStateCityMaster(models.Model):
#     """MCX state/city code mapping required by the KYC payload."""

#     state = models.CharField(max_length=100)
#     city = models.CharField(max_length=100)
#     state_city_code = models.CharField(max_length=50)

#     class Meta:
#         db_table = 'mcx_state_city_master'
#         constraints = [
#             models.UniqueConstraint(
#                 fields=('state', 'city'),
#                 name='mcx_state_city_unique',
#             ),
#         ]
#         ordering = ('state', 'city')


# class McxMaritalStatusMaster(models.Model):
#     marital_status = models.CharField(max_length=50, unique=True)
#     marital_code = models.CharField(max_length=50)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'mcx_marital_status_master'
#         ordering = ('marital_status',)


# class McxGenderMaster(models.Model):
#     gender = models.CharField(max_length=50, unique=True)
#     gender_code = models.CharField(max_length=50)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'mcx_gender_master'
#         ordering = ('gender',)


# class McxIncomeRangeMaster(models.Model):
#     income_range = models.CharField(max_length=50, unique=True)
#     income_code = models.CharField(max_length=50)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'mcx_income_range_master'
#         ordering = ('id',)


# class McxOccupationMaster(models.Model):
#     occupation_name = models.CharField(max_length=50, unique=True)
#     occupation_code = models.CharField(max_length=50)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'mcx_occupation_master'
#         ordering = ('occupation_name',)


# class McxAccountTypeMaster(models.Model):
#     account_type = models.CharField(max_length=50, unique=True)
#     account_code = models.CharField(max_length=50)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'mcx_account_type_master'
#         ordering = ('account_type',)


# class McxErrorCode(models.Model):
#     """Editable MCX provider error-code messages."""

#     code = models.CharField(max_length=3, unique=True)
#     message = (
#         models.CharField(max_length=MCX_ERROR_MESSAGE_MAX_LENGTH)
#         if MCX_ERROR_MESSAGE_MAX_LENGTH <= 255
#         else models.TextField()
#     )

#     class Meta:
#         db_table = 'mcx_error_code'
#         ordering = ('code',)

#     def __str__(self):
#         return f'{self.code} - {self.message}'


# def _credentialnsdlstr(col, **kw):
#     kw.setdefault('max_length', 50)
#     db_column = kw.pop('db_column', col)
#     return models.CharField(null=True, blank=True, db_column=db_column, **kw)


# def _nsdl_address_columns(
#     prefix,
#     suffixes=(
#         'Line1', 'Line2', 'Line3', 'Line4', 'Type',
#         'city', 'countrycode', 'statecode', 'zipcode',
#     ),
# ):
#     return tuple(
#         f'{prefix}{suffix}'
#         for suffix in suffixes
#     )


# NSDL_PRIMARY_COLUMNS = (
#     'name',
#     'shortName',
#     'pan',
#     'panFlag',
#     'grossAnnualIncome',
#     'dob',
#     'gender',
#     'mobile',
#     'email',
#     'aadhar',
#     'ddpiid',
#     'eStatement',
#     'signature',
#     *_nsdl_address_columns('coresAddress'),
#     *_nsdl_address_columns('permAddress'),
# )

# NSDL_ADDITIONAL_COLUMNS = (
#     'familyMobileFlag',
#     'familyEmailFlag',
#     'nominationOption',
#     'occupation',
#     'fatherOrHusbandName',
#     'dpId',
#     'clientId',
#     'sharePercentEqually',
#     'numOfNominees',
# )

# NSDL_BANK_ADDRESS_COLUMNS = (
#     *_nsdl_address_columns(
#         'address',
#         ('Line1', 'Line2', 'Line3', 'Line4', 'Type'),
#     ),
#     'zipcode',
# )

# NSDL_BANK_COLUMNS = (
#     'accountNumber',
#     'bankName',
#     'accountType',
#     'ifsc',
#     'micr',
#     *NSDL_BANK_ADDRESS_COLUMNS,
# )

# NSDL_NOMINEE_DETAILS_COLUMNS = (
#     'SeqNo', 'Name', 'Share', 'Dob', 'Minor', 'RelationWithNominee',
#     'MobileNum', 'EmailId',
# )

# NSDL_NOMINEE_IDENTIFICATION_COLUMNS = tuple(
#     f'Identification{suffix}'
#     for suffix in (
#         'Pan', 'Aadhar', 'DematAccId', 'SavingBankAccNo',
#     )
# )

# NSDL_NOMINEE_ADDRESS_COLUMNS = tuple(
#     f'address{suffix}'
#     for suffix in (
#         'Line1', 'Line2', 'Line3', 'Line4', 'Type', 'city',
#         'countrycode', 'statecode', 'zipcode',
#     )
# )

# NSDL_GUARDIAN_DETAILS_COLUMNS = (
#     'GuardianFlag', 'GuardianName', 'GuardianRelationship',
#     'GuardianMobileNum', 'GuardianEmailId',
# )

# NSDL_GUARDIAN_IDENTIFICATION_COLUMNS = tuple(
#     f'GuardianIdentification{suffix}'
#     for suffix in (
#         'Pan', 'Aadhar', 'DematAccId', 'SavingBankAccNo',
#     )
# )

# NSDL_GUARDIAN_ADDRESS_COLUMNS = tuple(
#     f'guardianAddress{suffix}'
#     for suffix in (
#         'Line1', 'Line2', 'Line3', 'Line4', 'Type', 'city',
#         'countrycode', 'Statecode', 'zipcode',
#     )
# )

# NSDL_NOMINEE_COLUMNS = (
#     *NSDL_NOMINEE_DETAILS_COLUMNS,
#     *NSDL_NOMINEE_IDENTIFICATION_COLUMNS,
#     *NSDL_NOMINEE_ADDRESS_COLUMNS,
#     *NSDL_GUARDIAN_DETAILS_COLUMNS,
#     *NSDL_GUARDIAN_IDENTIFICATION_COLUMNS,
#     *NSDL_GUARDIAN_ADDRESS_COLUMNS,
# )

# NSDL_COLUMNS = (
#     *NSDL_PRIMARY_COLUMNS,
#     *NSDL_ADDITIONAL_COLUMNS,
#     *NSDL_BANK_COLUMNS,
#     *(
#         f'nominee{number}{suffix}'
#         for number in (1, 2, 3)
#         for suffix in NSDL_NOMINEE_COLUMNS
#     ),
# )

# NSDL_NOMINEE_FIELDS = frozenset(
#     f'nominee{number}{suffix}'
#     for number in (1, 2, 3)
#     for suffix in NSDL_NOMINEE_COLUMNS
# )
# NSDL_GUARDIAN_COLUMNS = frozenset(
#     f'nominee{number}{suffix}'
#     for number in (1, 2, 3)
#     for suffix in (
#         *NSDL_GUARDIAN_DETAILS_COLUMNS,
#         *NSDL_GUARDIAN_IDENTIFICATION_COLUMNS,
#         *NSDL_GUARDIAN_ADDRESS_COLUMNS,
#     )
# )
# NSDL_NOMINATION_COLUMNS = frozenset({
#     'nominationOption',
#     'sharePercentEqually',
#     'numOfNominees',
# })
# NSDL_OPTIONAL_COLUMNS = frozenset(
#     NSDL_NOMINEE_FIELDS | NSDL_NOMINATION_COLUMNS
# )
# NSDL_MANDATORY_COLUMNS = frozenset(
#     set(NSDL_COLUMNS) - NSDL_OPTIONAL_COLUMNS
# )
# NSDL_COLUMN_MAX_LENGTHS = {column: 50 for column in NSDL_COLUMNS}

# def _nsdlstr(col, **kw):
#     # NSDL stores a wide provider payload with many configurable columns.
#     # Keep Django's max-length validation, but use TEXT in MySQL so the
#     # combined inline VARCHAR row does not exceed InnoDB's 8 KB limit.
#     kw.setdefault('max_length', NSDL_COLUMN_MAX_LENGTHS[col])
#     db_column = kw.pop('db_column', col)
#     required = col in NSDL_MANDATORY_COLUMNS
#     return models.TextField(
#         null=not required,
#         blank=not required,
#         **({'default': ''} if required else {}),
#         db_column=db_column,
#         **kw,
#     )

# def _nsdlpk(col):
#     return models.BigAutoField(primary_key=True, db_column=col)

# class Nsdl(models.Model):
#     """Configurable defaults for the online NSDL InstaDemat payload."""

#     id = _nsdlpk('id')
#     locals().update({column: _nsdlstr(column) for column in NSDL_COLUMNS})

#     class Meta:
#         db_table = 'nsdl'

#     def __str__(self):
#         return f"NSDL defaults {self.id}"

# class NsdlCredentials(models.Model):
#     id = models.BigAutoField(primary_key=True, db_column='id')
#     user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
#     requesterid = _credentialnsdlstr('requesterid')
#     certificate_file_name = _credentialnsdlstr('certificate_file_name')
#     private_key_file_password = _credentialnsdlstr('private_key_file_password')
#     private_key_filename = _credentialnsdlstr('private_key_filename')
#     ddpi_id = _credentialnsdlstr('ddpi_id')
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'nsdl_credentials'
#         unique_together = (('user', 'requesterid'),)

#     def __str__(self):
#         return f"{self.user_id or self.id} - {self.requesterid}"


# class CdslStateCodeMaster(models.Model):
#     state_name = models.CharField(max_length=50, unique=True)
#     state_code = models.CharField(max_length=6)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'cdsl_state_code_master'
#         ordering = ('state_name',)


# class CdslIncomeRangeMaster(models.Model):
#     income_range = models.CharField(max_length=50, unique=True)
#     income_code = models.CharField(max_length=6)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'cdsl_income_range_master'
#         ordering = ('id',)


# class NsdlStateCodeMaster(models.Model):
#     state_name = models.CharField(max_length=50, unique=True, db_column='state_name')
#     state_code = models.CharField(max_length=6, db_column='state_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'nsdl_state_code_master'
#         ordering = ('state_name',)


# class NsdlIncomeRangeMaster(models.Model):
#     income_range = models.CharField(max_length=50, unique=True, db_column='income_range')
#     income_code = models.CharField(max_length=12, db_column='income_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'nsdl_income_range_master'
#         ordering = ('id',)


# class NsdlOccupationMaster(models.Model):
#     occupation_name = models.CharField(max_length=50, unique=True, db_column='occupation_name')
#     occupation_code = models.CharField(max_length=50, db_column='occupation_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'nsdl_occupation_master'
#         ordering = ('occupation_name',)


# class NsdlRelationMaster(models.Model):
#     relation_name = models.CharField(max_length=50, unique=True, db_column='relation_name')
#     relation_code = models.CharField(max_length=50, db_column='relation_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'nsdl_relation_master'
#         ordering = ('relation_name',)


# class NsdlAccountTypeMaster(models.Model):
#     account_type = models.CharField(max_length=50, unique=True, db_column='account_type')
#     account_code = models.CharField(max_length=10, db_column='account_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'nsdl_account_type_master'
#         ordering = ('account_type',)


# class NsdlGenderMaster(models.Model):
#     gender = models.CharField(max_length=50, unique=True, db_column='gender')
#     gender_code = models.CharField(max_length=10, db_column='gender_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'nsdl_gender_master'
#         ordering = ('gender',)


# class NsdlCountryMaster(models.Model):
#     country = models.CharField(max_length=100, unique=True, db_column='country')
#     country_code = models.CharField(max_length=10, db_column='country_code')
#     created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')
#     updated_at = models.DateTimeField(auto_now=True, db_column='updated_at')

#     class Meta:
#         db_table = 'nsdl_country_master'
#         ordering = ('country',)


# class CdslUpload(models.Model):
#     user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
#     client = models.ForeignKey(UserDetails, on_delete=models.CASCADE, related_name='cdsl_uploads')
#     batch_number = models.CharField(max_length=5)
#     filename = models.CharField(max_length=100, blank=True)
#     acknowledgment_id = models.CharField(max_length=100, blank=True)
#     status = models.CharField(max_length=20, default='preparing', choices=[
#         (value, value) for value in ('preparing', 'prepared', 'submitting', 'pending', 'accepted', 'rejected', 'failed', 'unknown')
#     ])
#     row_count = models.PositiveIntegerField(default=0)
#     response = models.JSONField(default=dict, blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'cdsl_upload'
#         ordering = ('-id',)


# class CdslNominee(models.Model):
#     client = models.ForeignKey(UserDetails, on_delete=models.CASCADE, related_name='cdsl_nominees')
#     sequence = models.PositiveSmallIntegerField()
#     first_name = models.CharField(max_length=50)
#     middle_name = models.CharField(max_length=50, blank=True)
#     last_name = models.CharField(max_length=50, blank=True)
#     pan = models.CharField(max_length=10)
#     dob = models.DateField()
#     share = models.DecimalField(max_digits=5, decimal_places=2)
#     relationship_code = models.CharField(max_length=3)
#     address = models.CharField(max_length=108)
#     city = models.CharField(max_length=35)
#     state = models.ForeignKey(CdslStateCodeMaster, on_delete=models.PROTECT)
#     pincode = models.CharField(max_length=10)
#     mobile = models.CharField(max_length=15, blank=True)
#     email = models.EmailField(blank=True)

#     class Meta:
#         db_table = 'cdsl_nominee'
#         ordering = ('sequence',)
#         constraints = [models.UniqueConstraint(fields=('client', 'sequence'), name='cdsl_nominee_sequence')]

# class SchemaColumnMetadata(models.Model):
#     """Metadata for columns whose definitions live outside Django models."""
#     table_name = models.CharField(max_length=50)
#     column_name = models.CharField(max_length=50)
#     conditional_parameter = models.CharField(max_length=100, blank=True, default='')

#     class Meta:
#         db_table = 'schema_column_metadata'
#         constraints = [
#             models.UniqueConstraint(
#                 fields=('table_name', 'column_name'),
#                 name='schema_column_metadata_unique',
#             ),
#         ]
