from odoo import models, api, fields
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)

class CustomStockCron(models.Model):
    _name = 'custom.stock.cron'
    _description = 'Cron exclusivo para mercancía recibida'
    _auto = False

    @api.model
    def enviar_mercancia_infalible(self):
        """
        Cron: envía correos de 'mercancía' ÚNICAMENTE si ya cumplieron 24 horas
        desde su creación. No crea campos nuevos. Se apoya en tu filtro de
        notificaciones (_is_reception_notification) y excluye todo lo demás.
        """
        try:
            now = fields.Datetime.now()
            cutoff = now - timedelta(hours=24)

            Mail = self.env['mail.mail'].sudo()
            # 1) Candidatos: en cola, sin error y con antigüedad >= 24h
            domain = [
                ('state', '=', 'outgoing'),
                ('failure_reason', '=', False),
                ('create_date', '<=', cutoff),
            ]
            candidates = Mail.search(domain, order='create_date asc', limit=500)

            if not candidates:
                _logger.info("Cron mercancía: no hay candidatos >=24h.")
                return True

            # 2) Filtrar SOLO los de mercancía usando tu método
            #    (subject/body/plantilla con palabras clave)
            to_send = candidates.filtered(lambda m: m._is_reception_notification(m))
            if not to_send:
                _logger.info("Cron mercancía: no hay correos de mercancía >=24h.")
                return True

            _logger.info("Cron mercancía: %s correos a enviar (>=24h).", len(to_send))

            # 3) Enviar uno por uno (aislar fallos)
            for mail in to_send:
                try:
                    # Garantizar estado correcto
                    if mail.state != 'outgoing':
                        mail.write({'state': 'outgoing'})
                    # Envío directo (bypassa la cola normal)
                    mail.sudo().send(auto_commit=True)
                    _logger.info("Cron mercancía: enviado mail id=%s subj=%s",
                                 mail.id, (mail.subject or ''))
                except Exception:
                    _logger.exception("Cron mercancía: error enviando mail id=%s", mail.id)
                    # rollback local por si acaso
                    self._cr.rollback()

            return True

        except Exception:
            _logger.exception("Cron mercancía: ERROR GRAVE en enviar_mercancia_infalible()")
            return False

class MailMail(models.Model):
    _inherit = 'mail.mail'

    @api.model
    def process_email_queue(self, ids=None):
        """
        Sobrescribir el método para EXCLUIR COMPLETAMENTE nuestros correos específicos
        """
        # Si se pasan IDs específicos, procesar normalmente
        if ids:
            return super(MailMail, self).process_email_queue(ids)
        
        try:
            # Buscar TODOS los correos pendientes
            domain = [
                ('state', '=', 'outgoing'),
                ('failure_reason', '=', False)
            ]
            
            all_pending_mails = self.search(domain)
            
            if not all_pending_mails:
                return True
            
            # Filtrar EXCLUYENDO nuestros correos específicos
            mails_to_exclude = all_pending_mails.filtered(
                lambda mail: self._is_reception_notification(mail)
            )
            
            # Correos a procesar (excluyendo los nuestros)
            mails_to_process = all_pending_mails - mails_to_exclude
            
            if mails_to_process:
                _logger.info("📧 Procesando %d correos (excluyendo %d notificaciones)", 
                           len(mails_to_process), len(mails_to_exclude))
                return super(MailMail, self).process_email_queue(mails_to_process.ids)
            else:
                _logger.info("✅ Solo hay correos de notificación, no se procesa cola")
                return True
                
        except Exception as e:
            _logger.error("❌ Error en process_email_queue: %s", str(e))
            # En caso de error, procesar normalmente
            return super(MailMail, self).process_email_queue(ids)

    def _is_reception_notification(self, mail):
        """
        Determina si un correo es de notificación de recepción
        """
        # Método 1: Verificar por asunto
        subject = (mail.subject or '').lower()
        reception_keywords = ['recepción', 'mercancía', 'notificar', 'recibido']
        if any(keyword in subject for keyword in reception_keywords):
            return True
        
        # Método 2: Verificar por cuerpo del mensaje (si está disponible)
        body = (mail.body_html or mail.body or '').lower()
        if any(keyword in body for keyword in reception_keywords):
            return True
        
        # Método 3: Verificar por plantilla específica (si podemos acceder)
        try:
            if hasattr(mail, 'mail_template_id') and mail.mail_template_id:
                template_name = (mail.mail_template_id.name or '').lower()
                if 'notificar recepción' in template_name:
                    return True
        except:
            pass
            
        return False