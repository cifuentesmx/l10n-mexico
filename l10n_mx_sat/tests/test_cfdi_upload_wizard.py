# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
import zipfile
from io import BytesIO

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestCfdiUploadWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.company.write(
            {
                "vat": "EKU9003173C9",
                "country_id": cls.env.ref("base.mx").id,
            }
        )
        cls.env.user.groups_id |= cls.env.ref("l10n_mx_sat.group_sat_manager")
        cls.Wizard = cls.env["l10n_mx_sat.cfdi.upload.wizard"]
        cls.Document = cls.env["l10n_mx_sat.document"]

    def _minimal_cfdi_xml(self, receiver_rfc="EKU9003173C9", issuer_rfc="AAA010101AAA", uuid="AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"):
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
            f'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
            f'Fecha="2026-01-15T10:00:00" Total="100.00">'
            f'<cfdi:Emisor Rfc="{issuer_rfc}" Nombre="Emisor"/>'
            f'<cfdi:Receptor Rfc="{receiver_rfc}" Nombre="Receptor"/>'
            f"<cfdi:Complemento>"
            f'<tfd:TimbreFiscalDigital UUID="{uuid}" '
            f'FechaTimbrado="2026-01-15T10:01:00"/>'
            f"</cfdi:Complemento></cfdi:Comprobante>"
        ).encode()

    def _create_wizard(self, content, filename):
        return self.Wizard.create(
            {
                "company_id": self.company.id,
                "upload_file": base64.b64encode(content),
                "upload_filename": filename,
            }
        )

    def _build_zip(self, files):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            for name, content in files.items():
                zf.writestr(name, content)
        return buffer.getvalue()

    def test_upload_received_xml_creates_document(self):
        uuid = "11111111-2222-3333-4444-555555555555"
        wizard = self._create_wizard(
            self._minimal_cfdi_xml(uuid=uuid),
            "received.xml",
        )
        result = wizard.action_upload()
        document = self.Document.search(
            [
                ("uuid", "=", uuid),
                ("company_id", "=", self.company.id),
                ("direction", "=", "received"),
            ],
            limit=1,
        )
        self.assertTrue(document)
        self.assertTrue(document.has_xml)
        self.assertTrue(document.attachment_id)
        self.assertFalse(document.download_request_id)
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "success")

    def test_upload_issued_xml_detects_direction(self):
        uuid = "22222222-3333-4444-5555-666666666666"
        wizard = self._create_wizard(
            self._minimal_cfdi_xml(
                receiver_rfc="AAA010101AAA",
                issuer_rfc="EKU9003173C9",
                uuid=uuid,
            ),
            "issued.xml",
        )
        wizard.action_upload()
        document = self.Document.search(
            [
                ("uuid", "=", uuid),
                ("company_id", "=", self.company.id),
                ("direction", "=", "issued"),
            ],
            limit=1,
        )
        self.assertTrue(document)

    def test_upload_zip_processes_multiple_xml(self):
        uuid1 = "33333333-4444-5555-6666-777777777777"
        uuid2 = "44444444-5555-6666-7777-888888888888"
        zip_content = self._build_zip(
            {
                "received1.xml": self._minimal_cfdi_xml(uuid=uuid1),
                "issued1.xml": self._minimal_cfdi_xml(
                    receiver_rfc="AAA010101AAA",
                    issuer_rfc="EKU9003173C9",
                    uuid=uuid2,
                ),
            }
        )
        wizard = self._create_wizard(zip_content, "cfdi.zip")
        result = wizard.action_upload()
        self.assertTrue(
            self.Document.search([("uuid", "=", uuid1)], limit=1)
        )
        self.assertTrue(
            self.Document.search([("uuid", "=", uuid2)], limit=1)
        )
        self.assertIn("Processed: 2", result["params"]["message"])

    def test_upload_skips_xml_with_foreign_rfc(self):
        uuid = "55555555-6666-7777-8888-999999999999"
        wizard = self._create_wizard(
            self._minimal_cfdi_xml(
                receiver_rfc="BBB010101BBB",
                issuer_rfc="CCC010101CCC",
                uuid=uuid,
            ),
            "foreign.xml",
        )
        result = wizard.action_upload()
        self.assertFalse(self.Document.search([("uuid", "=", uuid)], limit=1))
        self.assertIn("Skipped: 1", result["params"]["message"])
        self.assertEqual(result["params"]["type"], "warning")

    def test_upload_rejects_unsupported_extension(self):
        wizard = self._create_wizard(b"not xml", "file.txt")
        with self.assertRaises(UserError):
            wizard.action_upload()

    def test_upload_rejects_invalid_zip(self):
        wizard = self._create_wizard(b"not-a-zip", "broken.zip")
        with self.assertRaises(UserError):
            wizard.action_upload()

    def test_open_cfdi_upload_wizard_action(self):
        action = self.company.action_l10n_mx_sat_open_cfdi_upload_wizard()
        self.assertEqual(action["res_model"], "l10n_mx_sat.cfdi.upload.wizard")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_company_id"], self.company.id)

    def test_upload_invalid_xml_counts_parse_error(self):
        wizard = self._create_wizard(b"<invalid xml", "broken.xml")
        result = wizard.action_upload()
        self.assertIn("Parse errors: 1", result["params"]["message"])
        self.assertEqual(result["params"]["type"], "warning")
