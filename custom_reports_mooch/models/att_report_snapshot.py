# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
from datetime import date, datetime, time as dtime
import logging

_logger = logging.getLogger('custom_reports_mooch.snapshot')


# ---------- Sanitizador JSON (nivel de módulo) ----------
def _json_sanitize(obj):
    """Convierte obj a algo 100% JSON-serializable.
    - Llaves de dict: str/int/float/bool/None; si no, se convierten a str/isoformat.
    - Valores: fechas -> ISO; recordsets -> lista de ids; set/tuple -> lista; fallback -> str().
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (datetime, date, dtime)):
        return obj.isoformat()
    if hasattr(obj, 'ids'):
        return list(obj.ids)
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, (str, int, float, bool)) or k is None:
                kk = k
            elif isinstance(k, (datetime, date, dtime)):
                kk = k.isoformat()
            else:
                kk = str(k)
            out[kk] = _json_sanitize(v)
        return out
    if isinstance(obj, (list, tuple, set)):
        return [_json_sanitize(x) for x in obj]
    return str(obj)


class AttReportSnapshot(models.Model):
    _name = 'att.report.snapshot'
    _description = 'Snapshot congelado de reporte de asistencias'
    _order = 'frozen_at desc'
    _rec_name = 'name'

    # Identidad del snapshot (rango libre según fechas del wizard)
    name = fields.Char(required=True, index=True)  # p.ej. "Operativos 2025-08-01..2025-08-31 (Tlajomulco)"
    period_type = fields.Selection([
        ('custom', 'Rango personalizado'),
        ('week', 'Semana ISO'),
        ('month', 'Mes'),
    ], required=True, default='custom', index=True)

    # Fechas exactas usadas por el usuario en el wizard
    date_from = fields.Datetime(required=True, index=True)
    date_to   = fields.Datetime(required=True, index=True)

    # Tipo de reporte (los 2 wizards)
    report_kind = fields.Selection([
        ('general', 'Operativos'),
        ('admin', 'Administrativos'),
    ], required=True, default='general', index=True)

    work_location_id = fields.Many2one('hr.work.location', string='Sucursal')
    employee_ids = fields.Many2many('hr.employee', string='Empleados incluidos')
    include_signature = fields.Boolean(default=True)

    # Dataset congelado (lo que se imprimió)
    frozen_dataset = fields.Json(string='Dataset congelado', help="Datos exactos con los que se generó el PDF.")
    frozen_at = fields.Datetime(string='Fecha de congelado', default=fields.Datetime.now, readonly=True)

    # Archivo PDF congelado
    pdf_file = fields.Binary(string='PDF', attachment=True)
    pdf_filename = fields.Char(string='Nombre archivo PDF')

    # Documentos (app documents)
    document_id = fields.Many2one('documents.document', string='Documento en Documentos')
    folder_id   = fields.Many2one('documents.folder', string='Carpeta Documentos')
    tag_ids     = fields.Many2many('documents.tag', string='Etiquetas')

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('frozen', 'Congelado'),
    ], default='draft', required=True)

    _sql_constraints = [
        ('uniq_custom_range_kind_loc',
         'unique(date_from, date_to, report_kind, work_location_id)',
         'Ya existe un snapshot con ese rango/tipo/sucursal.'),
    ]

    # --------- Helpers ----------
    @api.model
    def _ensure_folder(self, report_kind, work_location=False):
        """Devuelve carpeta base por tipo y, si hay sucursal, subcarpeta."""
        Folder = self.env['documents.folder']
        base_name = 'Asistencias - Administrativos' if report_kind == 'admin' else 'Asistencias - Operativos'
        base = Folder.search([('name', '=', base_name), ('parent_folder_id', '=', False)], limit=1)
        if not base:
            base = Folder.create({'name': base_name})
        if work_location:
            child = Folder.search([
                ('name', '=', work_location.name),
                ('parent_folder_id', '=', base.id)
            ], limit=1)
            if not child:
                child = Folder.create({'name': work_location.name, 'parent_folder_id': base.id})
            return child
        return base

    def _ensure_tags(self, work_location=False, date_from=False, date_to=False):
        """Crea/obtiene etiquetas bajo la categoría (facet) 'Asistencias'."""
        Tag = self.env['documents.tag']
        Facet = self.env['documents.facet']
        facet = Facet.search([('name', '=', 'Asistencias')], limit=1) or Facet.create({'name': 'Asistencias'})
        tag_ids = []
        if work_location:
            name = f"Sucursal: {work_location.name}"
            t = Tag.search([('name', '=', name), ('facet_id', '=', facet.id)], limit=1) or Tag.create({'name': name, 'facet_id': facet.id})
            tag_ids.append(t.id)
        if date_from and date_to:
            dfrom_str = fields.Date.to_date(date_from).strftime('%Y-%m-%d')
            dto_str   = fields.Date.to_date(date_to).strftime('%Y-%m-%d')
            name = f"Rango: {dfrom_str}..{dto_str}"
            t = Tag.search([('name', '=', name), ('facet_id', '=', facet.id)], limit=1) or Tag.create({'name': name, 'facet_id': facet.id})
            tag_ids.append(t.id)
        return [(6, 0, list(set(tag_ids)))] if tag_ids else False

    # --------- Render PDF (Odoo 17 safe) ----------
    def _render_pdf_from_dataset(self, dataset):
        """Renderiza el PDF alimentando la plantilla con el dataset congelado."""
        self.ensure_one()

        # Elegir el ir.actions.report correcto por tipo
        report_xmlid = (
            'custom_reports_mooch.action_attendance_admin_pdf'
            if self.report_kind == 'admin'
            else 'custom_reports_mooch.action_attendance_pdf'
        )

        _logger.info("SNAP_RENDER: report_xmlid=%s kind=%s", report_xmlid, self.report_kind)

        # Render directo con data['form'] para NO depender de un wizard vivo
        pdf_bytes, _ = self.env['ir.actions.report']._render_qweb_pdf(
            report_xmlid,
            [self.id],  # res_id dummy; el reporte tomará data['form']
            data={'form': dataset}
        )

        dfrom_str = fields.Date.to_date(self.date_from).strftime('%Y-%m-%d')
        dto_str   = fields.Date.to_date(self.date_to).strftime('%Y-%m-%d')
        base = "Administrativos" if self.report_kind == 'admin' else "Operativos"
        suffix = f" ({self.work_location_id.name})" if self.work_location_id else ""
        filename = f"{base}_{dfrom_str}_{dto_str}{suffix}.pdf"
        return pdf_bytes, filename

    # --------- Congelar desde wizard ----------
    def action_freeze_from_wizard_dataset(self, dataset):
        for rec in self:
            _logger.info(
                "SNAP_FREEZE: id=%s freeze dfrom=%s dto=%s tz=%s emps=%s kind=%s",
                rec.id,
                dataset.get('dfrom'),
                dataset.get('dto'),
                dataset.get('tz'),
                (dataset.get('employees').ids if hasattr(dataset.get('employees'), 'ids') else dataset.get('employees')),
                rec.report_kind,
            )

            # 1) Congelar dataset (100% JSON-safe)
            frozen = _json_sanitize(dataset)
            # Normalizar day_list si vino como datetime/date -> ISO (por seguridad)
            if frozen.get('day_list'):
                frozen['day_list'] = [
                    (x if isinstance(x, str) else (x.isoformat() if hasattr(x, 'isoformat') else str(x)))
                    for x in frozen['day_list']
                ]
            rec.frozen_dataset = frozen
            rec.frozen_at = fields.Datetime.now()

            # 2) Render PDF con el dataset CONGELADO
            pdf_bytes, filename = rec._render_pdf_from_dataset(frozen)
            rec.pdf_file = base64.b64encode(pdf_bytes)
            rec.pdf_filename = filename

            # 3) Publicar en Documentos (con subcarpeta por sucursal si aplica)
            folder = rec.folder_id or rec._ensure_folder(rec.report_kind, rec.work_location_id)
            rec.folder_id = folder.id
            tag_vals = rec._ensure_tags(rec.work_location_id, rec.date_from, rec.date_to)

            Attachment = self.env['ir.attachment']
            Documents = self.env['documents.document']

            if rec.document_id:
                att = rec.document_id.attachment_id
                if att:
                    att.write({'datas': rec.pdf_file, 'mimetype': 'application/pdf', 'name': filename})
                else:
                    new_att = Attachment.create({
                        'name': filename,
                        'type': 'binary',
                        'datas': rec.pdf_file,
                        'mimetype': 'application/pdf',
                        'res_model': 'documents.document',
                        'res_id': rec.document_id.id,
                    })
                    rec.document_id.write({'attachment_id': new_att.id})
                if tag_vals:
                    rec.document_id.write({'tag_ids': tag_vals})
            else:
                att = Attachment.create({
                    'name': filename,
                    'type': 'binary',
                    'datas': rec.pdf_file,
                    'mimetype': 'application/pdf',
                })
                vals = {
                    'name': rec.name,
                    'folder_id': folder.id,
                    'attachment_id': att.id,
                }
                if tag_vals:
                    vals['tag_ids'] = tag_vals
                rec.document_id = Documents.create(vals).id

            rec.state = 'frozen'
        return True

    # --------- Descargar PDF congelado ----------
    def action_print_frozen_pdf(self):
        """Descargar el PDF congelado (sin recalcular)."""
        self.ensure_one()
        if not self.pdf_file:
            raise UserError(_("Este snapshot no tiene PDF congelado."))
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{self._name}/{self.id}/pdf_file/{self.pdf_filename}?download=true",
            'target': 'self',
        }
