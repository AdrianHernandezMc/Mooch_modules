from odoo import api, models

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def create(self, vals):
        attachment = super().create(vals)
        # Si se subió al picking...
        if attachment.res_model == 'stock.picking':
            picking = self.env['stock.picking'].browse(attachment.res_id)
            # Solo recepciones entrantes
            if picking.picking_type_id.code == 'incoming':
                # Buscamos la PO cuyo name coincide con origin del picking
                po = self.env['purchase.order'].search(
                    [('name', '=', picking.origin)], limit=1
                )
                if po:
                    # Duplicamos el adjunto apuntando a la PO
                    attachment.copy({
                        'res_model': 'purchase.order',
                        'res_id': po.id,
                        # otras claves (e.g. 'public') se heredan
                    })
        return attachment
