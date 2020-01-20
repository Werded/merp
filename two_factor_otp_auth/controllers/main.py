# Copyright 2019 VentorTech OU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import http, _
from odoo.addons.web.controllers.main import Home
from odoo.http import request

import logging

_logger = logging.getLogger(__name__)

try:
    from two_factor_otp_auth.exceptions import MissingOtpError, InvalidOtpError

except IOError as error:
    _logger.debug(error)


class Login2fa(Home):

    @http.route()
    def web_login(self, redirect=None, **kw):
        try:
            response = super(Login2fa, self).web_login(redirect, **kw)
        except MissingOtpError:
            # user will came here only once during login process
            # - fists time after success validation of other credentials
            # to start Second Factor (OTP) validation step
            user_id = request.session.otk_uid
            user = request.env["res.users"].sudo().browse(user_id)
            values = request.params.copy()

            if user.qr_image_2fa or values.get("qr_code_2fa"):
                template = "two_factor_otp_auth.verify_code"
            else:
                template = "two_factor_otp_auth.scan_code"

                secret_code, qr_code = user._generate_qr_code()
                values.update({
                    "qr_code_2fa": qr_code,
                    "secret_code_2fa": secret_code,
                })

            response = request.render(
                template,
                values,
            )

        except InvalidOtpError:
            values = request.params.copy()
            values["error"] = _("Your security code is wrong")

            response = request.render(
                "two_factor_otp_auth.verify_code",
                values,
            )
        else:
            params = request.params
            if params.get("login_success"):
                user = request.env.user
                if user and user.enable_2fa and not user.qr_image_2fa:
                    # If credentials are Okay, but a user doesn't have
                    # QR code, that mean it's first success login with
                    # one-time-password. Now QR Code with it's Secret
                    # Code can be saved into the user.
                    params = request.params
                    values = {
                        "qr_image_2fa": params.get("qr_code_2fa"),
                        "secret_code_2fa": params.get("secret_code_2fa"),
                    }
                    user.sudo().write(values)

        return response
