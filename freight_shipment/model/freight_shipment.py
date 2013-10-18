#!/usr/bin/python
# -*- encoding: utf-8 -*-
###############################################################################
#    Module Writen to OpenERP, Open Source Management Solution
#    Copyright (C) OpenERP Venezuela (<http://www.vauxoo.com>).
#    All Rights Reserved
############# Credits #########################################################
#    Coded by: Katherine Zaoral <kathy@vauxoo.com>
#    Planified by: Yanina Aular <yani@vauxoo.com>, Humberto Arocha <hbto@vauxoo.com>
#    Audited by: Humberto Arocha <hbto@vauxoo.com>
###############################################################################
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################

from openerp.osv import fields, osv, orm
from openerp.tools.translate import _
from openerp import tools
import time


class stock_picking(osv.Model):

    _inherit = "stock.picking"
    _columns = {
        'freight_shipment_id': fields.many2one(
            'freight.shipment',
            string='Freight Shipment',
            help='Freight Shipment Order'
        ),
    }


class freight_shipment(osv.Model):

    _name = 'freight.shipment'
    _description = _('Freight Shipment')
    _inherit = ['mail.thread']

    '''
    Freight Shipment
    '''

    def _get_sale_order_ids(self, cr, uid, ids, field_name, arg, context=None):
        """
        """
        context = context or {}
        res = {}.fromkeys(ids, [])
        for fs_brw in self.browse(cr, uid, ids, context=context):
            for picking_brw in fs_brw.picking_ids:
                res[fs_brw.id] += [picking_brw.sale_id.id]
            res[fs_brw.id] = list(set(res[fs_brw.id]))

        return res

            #~ for so_brw in fs_brw.sale_order_ids:
                #~ for picking_brw in so_brw.picking_ids:
                    #~ if picking_brw.id in fs_picking_ids:
                        #~ res[fs_brw.id] += [picking_brw.id]

    _columns = {
        'name': fields.char(
            string='Number Reference',
            size=256,
            required=True,
            help='Number Reference'),
        'transport_unit_id': fields.many2one(
            'fleet.vehicle',
            string='Transport Unit',
            required=True,
            help='Transport Unit'),
        'pos_order_ids': fields.one2many(
            'pos.order', 'freight_shipment_id',
            string='POS Orders',
            help='POS Orders'),
        'state': fields.selection(
            [('draft','Draft'),
             ('awaiting','Waiting for Assignment'),
             ('exception','Exception'),
             ('confirm','Confirmed'),
             ('pending','Pending Dispatch'),
             ('overdue','Overdue'),
             ('in_transit','In Transit'),
             ('return','Return')],
            string='State',
            required=True,
            help=('Indicate Freight Shipment Order State. The possible states'
                  ' are:\n'
                  '\t- Draft: A rough copy of the document, just a draft.\n'
                  '\t- Waiting for Assignment: A freight.shipment order proposal'
                  ' that need to be corroborated\n'
                  '\t- Exception: The freight.shipment order is totally set.\n'
                  '\t- Confirmed: The delivery have been cheked and assigned.\n'
                  '\t- Pending Dispatch: Waiting for be delivery.\n'
                  '\t- Overdue: The freight.shipment is late.\n'
                  '\t- In Transit: Is already send to delivery.\n'
                  '\t- Return: The vehicle is return to the parking.\n'
            )),
        'weight': fields.float(
            string='Weight',
            help='Weight'
        ),
        'volumetric_weight': fields.float(
            string='Volumetric Weight',
            help='Volumetric Weight'
        ),
        'date': fields.datetime(
            string='Shipment Date',
            required=True,
            help='Date of the delivery was send'),
        'work_shift': fields.selection(
            [('morning', 'Morning'),
             ('afternoon', 'Afternoon'),
             ('night', 'Night')],
            string='Work Shift',
            required=True,
            help='Work Shift'),
        'zone_id': fields.many2one(
            'freight.zone',
            string='Zone',
            required=True,
            help='Zone'),
        'type': fields.selection(
            [('delivery', 'Delivery'),
             ('fleet', 'Fleet')],
            required=True,
            string='Type',
            help='Freight Type',
        ),
        'prefered_sale_order_ids': fields.one2many(
            'sale.order', 'prefered_freight_shipment_id',
            string='Prefered Sale Orders',
            help=('The Sale Orders who its prefered freight shipment was set'
                  ' with the current order.')
        ),
        'picking_ids': fields.one2many(
            'stock.picking', 'freight_shipment_id',
            string='Delivery Orders (Pickings)',
            help='Delivery Orders (Pickings)'
        ),
        'sale_order_ids': fields.function(
            fnct=_get_sale_order_ids,
            #~ 'sale_order_freight_shipment_rel',
            #~ 'fs_id', 'sale_order_id',
            type='many2many',
            relation='sale.order',
            string='Processed Sale Orders',
            help=('Sale Orders real send')
        ),
    }

    _defaults = {
        'state': 'draft',
        'work_shift': 'morning',
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    def action_prepare(self, cr, uid, ids, context=None):
        """
        Change the state of a freight.shipment order from 'draft' to 'awaiting'
        state (assigned order).
        @return: True
        """
        context = context or {}
        self.write(cr, uid, ids, {'state': 'awaiting'}, context=context)
        return True

    def action_assign(self, cr, uid, ids, context=None):
        """
        Change the state of a freight.shipment order from 'awaiting' to
        'exception' (if there is a problem with the freight.shipment order) or
        'confirm' is all the values were successfully valuated. 

        In the process it verify some conditions:

          - that the volumetrict weight  of the freight.shipment is less or
            equal to the fleet vehicle volumetric capacity.

        @return: True
        """
        context = context or {}
        exceptions = list()
        exception_msg = str()

        for fso_brw in self.browse(cr, uid, ids, context=context):
            exceptions.append(
                not self.check_volumetric_weight(
                    cr, uid, fso_brw.transport_unit_id.id,
                    fso_brw.volumetric_weight, context=context))
            if exceptions[-1]:
                exception_msg += _('The volumetric weight volume you are'
                    ' entering is greater than the volumetric capacity of'
                    ' youre transport unit (%s > %s).\n' %
                    (fso_brw.volumetric_weight,
                     fso_brw.transport_unit_id.volumetric_capacity))

        self.write(
            cr, uid, ids,
            {'state': any(exceptions) and 'exception' or 'confirm'},
            context=context)

        return True

    def action_force(self, cr, uid, ids, context=None):
        """
        This method force the freight.shipment to be confirm even if the
        valuation conditions of zone and burden are not fulfilled.
        """
        context = context or {}
        raise osv.except_osv(
            _('Warning'),
            _('This functionality is still in development'))
        return True


    def check_volumetric_weight(self, cr, uid, vehicle_id, volumetric_weight,
                                context=None):
        """
        Check if the freight.shipment order volumetric_weight value is
        less than th vehicle volumetric capacity.
        @param vehicle_id: fleet vehicle id
        @param volumetric_weight: freight.shipment order float value.
        @return: True if the current burdern is less than the vehicle
            volumetric weight. False if the current burdern is greater than the
            vehicle volumetric weight
        """
        context = context or {}
        fv_obj = self.pool.get('fleet.vehicle')
        fv_brw = fv_obj.browse(cr, uid, vehicle_id, context=context)
        return volumetric_weight <= fv_brw.volumetric_capacity \
               and True or False


class sale_order(osv.Model):

    _inherit = "sale.order"
    _columns = {
        'prefered_freight_shipment_id': fields.many2one(
            'freight.shipment',
            string='Prefered Freight Shipment',
            help=('Prefered Freight Shipment Order the users set when creating'
                  ' the Sale Order. This is the prefered Freight Shipment' 
                  ' where the sale order products will be send. Is not always'
                  'the real final destination')
        ),
        'freight_shipment_ids': fields.many2many(
            'freight.shipment',
            'sale_orders_freight_shipment_rel',
            'sale_order_id', 'fs_id',
            string='Final Freight Shipments',
            help=('It represent the real final destination Freight Shipment'
                  ' orders where this sale order was send.')
        ),
    }

    def _prepare_order_picking(self, cr, uid, order, context=None):
        """
        Overwrite the _prepare_order_picking method to add the prefered fregiht
        shipment order sete din the sale order to the pickings generating in
        the confirm sale order process.
        """
        context = context or {}
        res = super(sale_order, self)._prepare_order_picking(
            cr, uid, order, context=context)
        res.update(
            {'freight_shipment_id': order.prefered_freight_shipment_id.id})
        return res


class stock_move(osv.osv):
    _inherit = 'stock.move'

    def _prepare_chained_picking(self, cr, uid, picking_name, picking,
                                 picking_type, moves_todo, context=None):
        """
        Overwrithe method to add set the freight_shipment_id initial value
        when creating the dictionary to create the nre chained pickings.
        """
        context = context or {}
        res = super(stock_move, self)._prepare_chained_picking(
            cr, uid, picking_name, picking, picking_type, moves_todo,
            context=context)
        res.update({'freight_shipment_id': picking.freight_shipment_id.id})
        return res


class pos_order(osv.Model):

    _inherit = "pos.order"

    _columns = {
        'freight_shipment_id': fields.many2one(
            'freight.shipment',
            string='Freight Shipment',
            help='Freight Shipment'),
        'delivery': fields.boolean(
            string='Is Delivery?',
            help=('If this checkbox is checked then current order it or it'
                  ' will be delivery.')),
        'delivery_address': fields.many2one(
            'res.partner',
            'Delivery Address',
            help=('Delivery Address selected in the POS to make the delivery'
                  ' of the customer')),
    }
