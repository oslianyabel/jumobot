extractor_prompt = """
Se te enviarán conversaciones entre un cliente potencial y un asistente virtual. Necesito que extraigas la información de cada uno de los servicios sugeridos por el asistente virtual. En el caso de que se solicite un servicio a pagar por horas el campo product_uom_qty contendrá la cantidad de horas solicitadas por el usuario, en caso contrario será 1 su valor. El campo product_uom ponlo por defecto en 1.
"""

extra = """
A continuación te comparto el listado de los servicios disponibles en la empresa, si encuentras alguno de ellos en la conversación y falta algún campo puedes tomarlo de aquí: \n
[
  {
	"product_name": "Desarrollo Odoo",
	"product_id": 605,
	"price_unit": 17,
	"product_uom": 1,
	"discount": 0,
  },
  {
	"product_name": "Implantación Odoo",
	"product_id": 622,
	"price_unit": 50,
	"product_uom": 1,
	"discount": 0,
  },
  {
	"product_name": "Upgrade Odoo",
	"product_id": 944,
	"price_unit": 3500,
	"product_uom": 1,
	"discount": 0,
  },
  {
	"product_name": "Fabrica IA",
	"product_id": 1069,
	"price_unit": 10000,
	"product_uom": 1,
	"discount": 0,
  }
]
Servicios de nombres similares serán aceptados pero servicios completamente diferentes ignóralos.
Por favor, responde estrictamente en el siguiente formato JSON:
[
  {
	"product_name": "string",
	"product_id": number,
	"price_unit": number,
	"product_uom": number,
	"discount": number,
	"product_uom_qty": number
  }
]
Ejemplo:
[
  {
	"product_name": "Desarrollo Odoo",
	"product_id": 605,
	"price_unit": 17,
	"product_uom": 1,
	"discount": 0,
	"product_uom_qty": 40
  },
]
"""
