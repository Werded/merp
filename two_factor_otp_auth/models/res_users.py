# Copyright 2019 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import base64
import os
import tempfile

from odoo import fields, models, api, _
from odoo.exceptions import AccessError
from odoo.http import request

import logging

_logger = logging.getLogger(__name__)

try:
    import pyotp
    import qrcode

except ImportError as error:
    _logger.debug(error)

try:
    from two_factor_otp_auth.exceptions import MissingOtpError, InvalidOtpError

except IOError as err:
    _logger.debug(err)


class ResUsers(models.Model):
    _inherit = 'res.users'

    enable_2fa = fields.Boolean(
        string='Two Factor Authentication',
        inverse="_inverse_enable_2fa",
    )
    secret_code_2fa = fields.Char(
        string='Two Factor Authentication Secret Code',
        old_name="secret_code",  # too common
        copy=False,
    )
    qr_image_2fa = fields.Binary(
        string='Two Factor Authentication QR Code',
        copy=False,
    )

    def _inverse_enable_2fa(self):
        """
        Inverse `enable_2fa` - call `action_discard_2f_auth_credentials` method
        if value of the field become `false`
        """
        for user in self:
            if not user.enable_2fa:
                user.action_discard_2f_auth_credentials()

    def action_discard_2f_auth_credentials(self):
        """
        Remove values from fields `qr_image_2fa`, `auth_secret_code_2fa`
        """
        values = {
            "qr_image_2fa": False,
            "secret_code_2fa": False,
        }
        self.write(values)

    def action_disable_2f_auth(self):
        """
        Set `enable_2fa` field value to `False`. Check access for action
        via `_can_change_2f_auth_settings`.
        """
        self._can_change_2f_auth_settings()
        values = {
            "enable_2fa": False,
        }
        self.write(values)

    def action_enable_2f_auth(self):
        """
        Set `enable_2fa` field value to `False`. Check access for action
        via `_can_change_2f_auth_settings`.
        """
        self._can_change_2f_auth_settings()
        values = {
            "enable_2fa": True,
        }
        self.write(values)

    def _check_credentials(self, password):
        """
        Overload core method to also check Two Factor Authentication
        credentials.

        Raises:
         * odoo.addons.two_factor_otp_auth.exceptions.MissingOtpError - no
            `otp_code` in request params. Should be caught by controller and
            render and open enter "one-time-password" page or QR code creation
        """
        self.ensure_one()
        super(ResUsers, self)._check_credentials(password)
        if self.enable_2fa:
            params = request.params
            secret_code = self.secret_code_2fa or params.get("secret_code_2fa")
            if params.get("otp_code") is None:
                request.session.otk_uid = self.id
                raise MissingOtpError()
            else:
                # cat trigger `InvalidOtpError`
                self._check_otp_code(
                    params.get("otp_code"),
                    secret_code,
                )

    def _generate_qr_code(self):

        self.ensure_one()

        company = self.env['res.company'].browse(self.company_id.id)
        key = base64.b32encode(os.urandom(10)).decode('utf-8')
        code = pyotp.totp.TOTP(key)
        img = qrcode.make(
            code.provisioning_uri(
                self.login,
                issuer_name=company.name,
            )
        )
        _, file_path = tempfile.mkstemp()
        img.save(file_path)

        with open(file_path, 'rb') as image_file:
            qr_image_code = base64.b64encode(
                image_file.read(),
            )
        data = (key, qr_image_code)
        return data

    @api.model
    def _can_change_2f_auth_settings(self):
        """
        Check that current user can make mass actions with Two Factor
        Authentication settings.

        Raises:
         * odoo.exceptions.AccessError: only administrators can do this
           action

        TODO:
         * Rewrite text of warning - add list of groups with access
         * Or even better create separate group.
        """
        if not self.env.user._is_admin():
            raise AccessError(_(
                "Only Administrators can do this operation!"
            ))

    @staticmethod
    def _check_otp_code(otp, secret):
        """
        Validate incoming one time password `otp` witch secret via `pyotp`
        library methods.

        Args:
         * otp(str/integer) - one time password
         * secret(srt) - origin secret of QR Code for one time password
            generator

        Raises:
         * odoo.addons.two_factor_otp_auth.exceptions.InvalidOtpError -
            one-time-password. Should be caught by controller and return user
            to enter "one-time-password" page

        Returns:
         * bool - True
        """
        totp = pyotp.TOTP(secret)
        str_otp = str(otp)
        verify = totp.verify(str_otp)
        if not verify:
            raise InvalidOtpError()
        return True
