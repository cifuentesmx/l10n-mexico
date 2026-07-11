# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
import zipfile
from io import BytesIO

from lxml import etree

from odoo import fields, models
from odoo.exceptions import UserError

from ..services.sat_helpers import SAFE_XML_PARSER

_ZIP_MAX_SIZE = 500 * 1024 * 1024
_ZIP_MAX_FILES = 10_000


class L10nMxSatCfdiUploadWizard(models.TransientModel):
    _name = "l10n_mx_sat.cfdi.upload.wizard"
    _description = "SAT CFDI Upload Wizard"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    upload_file = fields.Binary(
        string="File",
        required=True,
        attachment=False,
    )
    upload_filename = fields.Char(string="Filename")

    def action_upload(self):
        """Process uploaded XML or ZIP and create/update SAT documents."""
        self.ensure_one()
        if not self.upload_file:
            raise UserError(self.env._("Upload an XML or ZIP file first."))

        filename = (self.upload_filename or "").lower()
        if not filename.endswith((".xml", ".zip")):
            raise UserError(
                self.env._("Unsupported file type. Upload an XML or ZIP file.")
            )

        file_data = base64.b64decode(self.upload_file)
        Document = self.env["l10n_mx_sat.document"]
        company = self.company_id

        processed = 0
        skipped = 0
        parse_errors = 0

        for xml_bytes in self._iter_xml_contents(file_data, filename):
            try:
                tree = etree.fromstring(xml_bytes, SAFE_XML_PARSER)
            except etree.XMLSyntaxError:
                parse_errors += 1
                continue

            direction = self._detect_direction(tree, company)
            if not direction:
                skipped += 1
                continue

            upload_context = self._make_upload_context(direction)
            document = Document._upsert_from_xml(
                tree, xml_bytes, company, upload_context
            )
            if document:
                processed += 1
            else:
                skipped += 1

        return self._build_result_notification(processed, skipped, parse_errors)

    def _iter_xml_contents(self, file_data, filename):
        """Yield raw XML bytes from a single XML file or a ZIP archive."""
        if filename.endswith(".xml"):
            yield file_data
            return

        try:
            with zipfile.ZipFile(BytesIO(file_data)) as zf:
                total_size = sum(info.file_size for info in zf.infolist())
                file_count = len(zf.namelist())
                if total_size > _ZIP_MAX_SIZE or file_count > _ZIP_MAX_FILES:
                    raise UserError(
                        self.env._(
                            "The ZIP file exceeds the allowed size or file count."
                        )
                    )
                for name in zf.namelist():
                    if not name.lower().endswith(".xml"):
                        continue
                    yield zf.read(name)
        except zipfile.BadZipFile as err:
            raise UserError(
                self.env._("The uploaded file is not a valid ZIP archive.")
            ) from err

    def _detect_direction(self, tree, company):
        """Return issued/received when the company RFC matches emisor/receptor."""
        Document = self.env["l10n_mx_sat.document"]
        company_rfc = Document._get_company_rfc(company)
        if not company_rfc:
            return False

        emisor = tree.find("{*}Emisor")
        receptor = tree.find("{*}Receptor")
        emisor_rfc = (emisor.get("Rfc") or "").upper() if emisor is not None else ""
        receptor_rfc = (
            (receptor.get("Rfc") or "").upper() if receptor is not None else ""
        )

        if emisor_rfc == company_rfc:
            return "issued"
        if receptor_rfc == company_rfc:
            return "received"
        return False

    def _make_upload_context(self, direction):
        """Lightweight context object for manual uploads without SAT requests."""
        return type(
            "CfdiUploadContext",
            (),
            {
                "id": False,
                "document_kind": "cfdi",
                "direction": direction,
            },
        )()

    def _build_result_notification(self, processed, skipped, parse_errors):
        message = self.env._(
            "Processed: %(processed)s. Skipped: %(skipped)s. "
            "Parse errors: %(parse_errors)s.",
            processed=processed,
            skipped=skipped,
            parse_errors=parse_errors,
        )
        notif_type = "success" if processed else "warning"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("CFDI upload"),
                "message": message,
                "type": notif_type,
                "sticky": not processed,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
