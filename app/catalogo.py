"""Catálogo de las 14 tablas que administra el aplicativo.

Cada tabla se describe con un objeto Entidad (sus campos, cómo listarla y
qué procedimientos llamar). Las pantallas de mantenimiento son genéricas:
leen esta descripción y construyen la lista, el formulario y las llamadas
a los procedimientos. Para agregar o cambiar un campo basta editar este
archivo.

Las tablas que dependen de otra (teléfonos de una entidad, ítems de una
propuesta...) no tienen pantalla propia: se declaran como Detalle de su
tabla principal y se administran dentro de la pantalla de esta. El menú
lateral (MENU) solo muestra las tablas principales.

Tipos de campo:
    texto, texto_largo, entero, decimal, fecha, booleano,
    opcion      lista fija de valores (los mismos del CHECK de la tabla)
    referencia  valor de otra tabla (clave foránea), elegido de una lista
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Campo:
    """Una columna de la tabla tal como se muestra en el formulario."""

    nombre: str                     # nombre de la columna en la tabla
    etiqueta: str                   # texto que ve el usuario
    tipo: str = "texto"
    obligatorio: bool = False
    clave: bool = False             # forma parte de la clave primaria
    editable_en_clave: bool = False  # clave que sí se puede cambiar al modificar
    auto: bool = False              # si se deja vacío lo genera un trigger
    opciones: tuple = ()            # para tipo "opcion"
    referencia: str = ""            # SELECT valor, descripcion  (tipo "referencia")
    depende_de: str = ""            # campo cuyo valor filtra la referencia (%s)
    largo: int = 0                  # máximo de caracteres (0 = sin límite visible)
    ayuda: str = ""                 # pista que aparece bajo el control
    por_defecto: object = None      # valor inicial al crear (o función sin argumentos)

    def valor_inicial(self):
        """Valor con el que aparece el campo en un formulario nuevo."""
        return self.por_defecto() if callable(self.por_defecto) else self.por_defecto


@dataclass
class Detalle:
    """Tabla dependiente que se administra dentro de la pantalla de su tabla principal."""

    tabla: str                      # tabla dependiente (hija)
    titulo: str                     # texto de la pestaña
    enlace: dict                    # {campo de la hija: campo de la tabla principal}
    ocultar: tuple = ()             # columnas de la lista hija que ya se ven en la principal


@dataclass
class Entidad:
    """Una tabla del modelo y la forma de administrarla."""

    tabla: str
    titulo: str                     # plural, para el menú y la cabecera
    singular: str                   # para los mensajes ("Empresa registrada")
    descripcion: str
    campos: list
    consulta_lista: str             # SELECT con TODAS las columnas de la tabla (+ extras)
    columnas_lista: list            # (columna, encabezado) visibles en la lista
    args_actualizar: list = field(default_factory=list)  # "@x" = valor original de x
    acciones: list = field(default_factory=list)          # botones extra: (texto, id)
    detalles: list = field(default_factory=list)          # tablas dependientes (Detalle)
    resumen: tuple = ()             # columnas que describen un registro ("razon_social",)

    # Nombres de los procedimientos (convención de 04_procedimientos.sql)
    @property
    def proc_insertar(self) -> str:
        return f"sp_{self.tabla}_insertar"

    @property
    def proc_actualizar(self) -> str:
        return f"sp_{self.tabla}_actualizar"

    @property
    def proc_eliminar(self) -> str:
        return f"sp_{self.tabla}_eliminar"

    @property
    def claves(self) -> list:
        return [c.nombre for c in self.campos if c.clave]

    def campo(self, nombre: str) -> Campo:
        return next(c for c in self.campos if c.nombre == nombre)

    def argumentos_insertar(self, valores: dict) -> list:
        """Argumentos de sp_<tabla>_insertar: todas las columnas en orden."""
        return [valores.get(c.nombre) for c in self.campos]

    def argumentos_actualizar(self, valores: dict, originales: dict) -> list:
        """Argumentos de sp_<tabla>_actualizar ("@x" toma el valor original)."""
        if not self.args_actualizar:
            return [valores.get(c.nombre) for c in self.campos]
        return [originales.get(a[1:]) if a.startswith("@") else valores.get(a)
                for a in self.args_actualizar]

    def argumentos_eliminar(self, originales: dict) -> list:
        """Argumentos de sp_<tabla>_eliminar: la clave primaria."""
        return [originales.get(c) for c in self.claves]


# ----------------------------------------------------------------------
# Consultas de referencia (listas desplegables de claves foráneas)
# ----------------------------------------------------------------------
REF_EMPRESAS = "SELECT numero_ruc, razon_social FROM empresa ORDER BY razon_social"
REF_ENTIDADES = "SELECT ruc_entidad, razon_social FROM entidad_contratante ORDER BY razon_social"
REF_MARCAS = "SELECT DISTINCT marca, marca FROM modelo_equipo ORDER BY 1"
REF_MODELOS = "SELECT modelo, tipo_equipo FROM modelo_equipo WHERE marca = %s ORDER BY 1"
REF_PLACAS = ("SELECT m.placa, m.marca || ' ' || m.modelo || ' - ' || me.tipo_equipo "
              "FROM maquinaria m JOIN modelo_equipo me USING (marca, modelo) ORDER BY 1")
REF_LICITACIONES = ("SELECT codigo_licitacion, estado || ' - ' || left(objeto, 70) "
                    "FROM licitacion ORDER BY 1 DESC")
REF_REPRESENTANTES = ("SELECT dni, concat_ws(' ', nombres, apellido_paterno, apellido_materno) "
                      "FROM representante_legal ORDER BY 2")
REF_CUENTAS = ("SELECT c.codigo_cci, c.entidad_bancaria || ' - ' || e.razon_social "
               "FROM cuenta_bancaria c JOIN empresa e ON e.numero_ruc = c.ruc_titular ORDER BY 1")
REF_PROPUESTAS = ("SELECT p.codigo_propuesta, p.codigo_licitacion || ' - ' || l.estado "
                  "FROM propuesta_comercial p JOIN licitacion l USING (codigo_licitacion) "
                  "ORDER BY 1 DESC")

# Valores permitidos (idénticos a los CHECK de 01_crear_tablas.sql)
ESTADOS_CONTRIBUYENTE = ("ACTIVO", "SUSPENSIÓN TEMPORAL", "BAJA PROVISIONAL",
                         "BAJA DEFINITIVA", "BAJA DE OFICIO")
CONDICIONES_CONTRIBUYENTE = ("HABIDO", "NO HABIDO", "NO HALLADO")
TIPOS_REGISTRO_RNP = ("PROVEEDOR DE BIENES", "PROVEEDOR DE SERVICIOS",
                      "CONSULTOR DE OBRAS", "EJECUTOR DE OBRAS")
ESTADOS_RNP = ("VIGENTE", "SUSPENDIDA", "NO VIGENTE")
TIPOS_PROCESO = ("CONTRATO MENOR", "LICITACIÓN PÚBLICA", "LICITACIÓN PÚBLICA ABREVIADA",
                 "CONCURSO PÚBLICO", "CONCURSO PÚBLICO ABREVIADO", "COMPARACIÓN DE PRECIOS", "OTRO")
ESTADOS_LICITACION = ("REGISTRADA", "EN PREPARACIÓN", "PRESENTADA", "ADJUDICADA",
                      "NO ADJUDICADA", "CANCELADA")
UNIDADES_MEDIDA = ("HORA", "DÍA", "MES", "UNIDAD", "SERVICIO", "GLOBAL")

#: Menú lateral: (sección, tablas principales). Las demás tablas son detalles.
MENU = [
    ("Procesos", ["licitacion", "propuesta_comercial"]),
    ("Datos maestros", ["entidad_contratante", "empresa", "maquinaria", "modelo_equipo"]),
]


ENTIDADES = [
    # ------------------------------------------------------------------
    # Empresa y sus tablas dependientes
    # ------------------------------------------------------------------
    Entidad(
        tabla="empresa", titulo="Empresas", singular="Empresa",
        descripcion="Contribuyentes con RUC: la empresa postora y las propietarias de equipos. "
                    "Seleccione una empresa para gestionar sus habilitaciones RNP, representantes "
                    "y cuentas bancarias.",
        resumen=("razon_social",),
        detalles=[
            Detalle("habilitacion_rnp", "Habilitaciones RNP", {"numero_ruc": "numero_ruc"},
                    ocultar=("numero_ruc", "empresa")),
            Detalle("representante_legal", "Representantes legales", {"ruc_empresa": "numero_ruc"},
                    ocultar=("empresa",)),
            Detalle("cuenta_bancaria", "Cuentas bancarias", {"ruc_titular": "numero_ruc"},
                    ocultar=("ruc_titular", "titular")),
        ],
        campos=[
            Campo("numero_ruc", "RUC", obligatorio=True, clave=True, largo=11, ayuda="11 dígitos"),
            Campo("razon_social", "Razón social", obligatorio=True, largo=150),
            Campo("estado_contribuyente", "Estado SUNAT", "opcion", obligatorio=True,
                  opciones=ESTADOS_CONTRIBUYENTE, por_defecto="ACTIVO"),
            Campo("condicion_contribuyente", "Condición SUNAT", "opcion", obligatorio=True,
                  opciones=CONDICIONES_CONTRIBUYENTE, por_defecto="HABIDO"),
            Campo("domicilio_fiscal", "Domicilio fiscal", obligatorio=True, largo=255),
            Campo("fecha_verificacion_sunat", "Verificado en SUNAT el", "fecha", obligatorio=True,
                  por_defecto=date.today),
        ],
        consulta_lista="SELECT * FROM empresa ORDER BY razon_social",
        columnas_lista=[("numero_ruc", "RUC"), ("razon_social", "Razón social"),
                        ("estado_contribuyente", "Estado"), ("condicion_contribuyente", "Condición"),
                        ("fecha_verificacion_sunat", "Verificado"),
                        ("domicilio_fiscal", "Domicilio fiscal")],
    ),
    Entidad(
        tabla="habilitacion_rnp", titulo="Habilitaciones RNP", singular="Habilitación RNP",
        descripcion="Inscripción de la empresa en los registros del RNP (OSCE).",
        campos=[
            Campo("numero_ruc", "Empresa", "referencia", obligatorio=True, clave=True,
                  referencia=REF_EMPRESAS),
            Campo("tipo_registro", "Registro", "opcion", obligatorio=True, clave=True,
                  opciones=TIPOS_REGISTRO_RNP, por_defecto="PROVEEDOR DE SERVICIOS"),
            Campo("fecha_inicio_vigencia", "Inicio de vigencia", "fecha", obligatorio=True),
            Campo("estado_inscripcion", "Estado", "opcion", obligatorio=True,
                  opciones=ESTADOS_RNP, por_defecto="VIGENTE"),
            Campo("fecha_verificacion", "Verificado en RNP el", "fecha", obligatorio=True,
                  por_defecto=date.today),
        ],
        consulta_lista=("SELECT h.*, e.razon_social AS empresa FROM habilitacion_rnp h "
                        "JOIN empresa e USING (numero_ruc) ORDER BY e.razon_social, h.tipo_registro"),
        columnas_lista=[("numero_ruc", "RUC"), ("empresa", "Empresa"),
                        ("tipo_registro", "Registro"), ("estado_inscripcion", "Estado"),
                        ("fecha_inicio_vigencia", "Vigente desde"),
                        ("fecha_verificacion", "Verificado")],
    ),
    Entidad(
        tabla="representante_legal", titulo="Representantes legales", singular="Representante",
        descripcion="Personas con poder para suscribir propuestas y declaraciones.",
        campos=[
            Campo("dni", "DNI", obligatorio=True, clave=True, largo=8, ayuda="8 dígitos"),
            Campo("nombres", "Nombres", obligatorio=True, largo=60),
            Campo("apellido_paterno", "Apellido paterno", obligatorio=True, largo=40),
            Campo("apellido_materno", "Apellido materno", largo=40),
            Campo("cargo", "Cargo", obligatorio=True, largo=50),
            Campo("correo_notificacion", "Correo de notificación", obligatorio=True, largo=100),
            Campo("telefono", "Teléfono", largo=15, ayuda="solo dígitos"),
            Campo("ruc_empresa", "Empresa", "referencia", obligatorio=True, referencia=REF_EMPRESAS),
        ],
        consulta_lista=("SELECT r.*, e.razon_social AS empresa FROM representante_legal r "
                        "JOIN empresa e ON e.numero_ruc = r.ruc_empresa ORDER BY r.apellido_paterno"),
        columnas_lista=[("dni", "DNI"), ("nombres", "Nombres"),
                        ("apellido_paterno", "Ap. paterno"), ("apellido_materno", "Ap. materno"),
                        ("cargo", "Cargo"), ("correo_notificacion", "Correo"),
                        ("telefono", "Teléfono"), ("empresa", "Empresa")],
    ),
    Entidad(
        tabla="cuenta_bancaria", titulo="Cuentas bancarias", singular="Cuenta bancaria",
        descripcion="Cuentas (CCI) en las que se autoriza abonar los pagos.",
        campos=[
            Campo("codigo_cci", "Código CCI", obligatorio=True, clave=True, largo=20, ayuda="20 dígitos"),
            Campo("entidad_bancaria", "Banco", obligatorio=True, largo=100),
            Campo("ruc_titular", "Empresa titular", "referencia", obligatorio=True, referencia=REF_EMPRESAS),
        ],
        consulta_lista=("SELECT c.*, e.razon_social AS titular FROM cuenta_bancaria c "
                        "JOIN empresa e ON e.numero_ruc = c.ruc_titular ORDER BY e.razon_social"),
        columnas_lista=[("codigo_cci", "CCI"), ("entidad_bancaria", "Banco"),
                        ("ruc_titular", "RUC titular"), ("titular", "Titular")],
    ),

    # ------------------------------------------------------------------
    # Maquinaria
    # ------------------------------------------------------------------
    Entidad(
        tabla="modelo_equipo", titulo="Modelos de equipo", singular="Modelo de equipo",
        descripcion="Especificaciones técnicas de cada modelo de fabricante.",
        campos=[
            Campo("marca", "Marca", obligatorio=True, clave=True, largo=50),
            Campo("modelo", "Modelo", obligatorio=True, clave=True, largo=50),
            Campo("tipo_equipo", "Tipo de equipo", obligatorio=True, largo=60),
            Campo("capacidad_ton", "Capacidad (t)", "decimal", obligatorio=True),
        ],
        consulta_lista="SELECT * FROM modelo_equipo ORDER BY marca, modelo",
        columnas_lista=[("marca", "Marca"), ("modelo", "Modelo"),
                        ("tipo_equipo", "Tipo de equipo"), ("capacidad_ton", "Capacidad (t)")],
    ),
    Entidad(
        tabla="maquinaria", titulo="Maquinaria", singular="Equipo",
        descripcion="Unidades de equipo, propias o subcontratadas, que se ofrecen en las propuestas. "
                    "Seleccione un equipo para gestionar sus certificados de inspección.",
        resumen=("marca", "modelo"),
        detalles=[
            Detalle("certificado_maquinaria", "Certificados de inspección", {"placa": "placa"},
                    ocultar=("placa",)),
        ],
        campos=[
            Campo("placa", "Placa", obligatorio=True, clave=True, largo=10, ayuda="ej. AEJ-831"),
            Campo("marca", "Marca", "referencia", obligatorio=True, referencia=REF_MARCAS),
            Campo("modelo", "Modelo", "referencia", obligatorio=True, referencia=REF_MODELOS,
                  depende_de="marca"),
            Campo("serie", "Serie", largo=30),
            Campo("marca_vehiculo", "Marca del vehículo", largo=50),
            Campo("ruc_propietario", "Propietario", "referencia", obligatorio=True,
                  referencia=REF_EMPRESAS),
        ],
        consulta_lista=("SELECT m.*, me.tipo_equipo, e.razon_social AS propietario FROM maquinaria m "
                        "JOIN modelo_equipo me USING (marca, modelo) "
                        "JOIN empresa e ON e.numero_ruc = m.ruc_propietario ORDER BY m.placa"),
        columnas_lista=[("placa", "Placa"), ("marca", "Marca"), ("modelo", "Modelo"),
                        ("tipo_equipo", "Tipo"), ("serie", "Serie"),
                        ("marca_vehiculo", "Vehículo"), ("propietario", "Propietario")],
    ),
    Entidad(
        tabla="certificado_maquinaria", titulo="Certificados de inspección", singular="Certificado",
        descripcion="Sin certificado vigente, el equipo no puede asignarse a una propuesta (RA2).",
        campos=[
            Campo("codigo_certificado", "Código", obligatorio=True, clave=True, largo=50),
            Campo("entidad_certificadora", "Entidad certificadora", obligatorio=True, largo=100),
            Campo("normativa", "Normativa", obligatorio=True, largo=100, ayuda="ej. ASME B30.22"),
            Campo("fecha_inspeccion", "Fecha de inspección", "fecha", obligatorio=True),
            Campo("fecha_caducidad", "Fecha de caducidad", "fecha", obligatorio=True),
            Campo("placa", "Equipo", "referencia", obligatorio=True, referencia=REF_PLACAS),
        ],
        consulta_lista=("SELECT c.*, CASE WHEN c.fecha_caducidad < CURRENT_DATE THEN 'VENCIDO' "
                        "WHEN c.fecha_caducidad - CURRENT_DATE <= 30 THEN 'POR VENCER' "
                        "ELSE 'VIGENTE' END AS vigencia "
                        "FROM certificado_maquinaria c ORDER BY c.placa, c.fecha_caducidad DESC"),
        columnas_lista=[("codigo_certificado", "Código"), ("placa", "Placa"),
                        ("normativa", "Normativa"), ("fecha_inspeccion", "Inspección"),
                        ("fecha_caducidad", "Caducidad"), ("vigencia", "Vigencia"),
                        ("entidad_certificadora", "Certificadora")],
    ),

    # ------------------------------------------------------------------
    # Entidad contratante y sus teléfonos
    # ------------------------------------------------------------------
    Entidad(
        tabla="entidad_contratante", titulo="Entidades contratantes", singular="Entidad contratante",
        descripcion="Entidades públicas que convocan los procesos de contratación. Seleccione "
                    "una entidad para gestionar sus teléfonos de contacto.",
        resumen=("razon_social",),
        detalles=[
            Detalle("telefono_entidad", "Teléfonos", {"ruc_entidad": "ruc_entidad"},
                    ocultar=("ruc_entidad", "entidad")),
        ],
        campos=[
            Campo("ruc_entidad", "RUC", obligatorio=True, clave=True, largo=11,
                  ayuda="11 dígitos, empieza con 20"),
            Campo("razon_social", "Razón social", obligatorio=True, largo=150),
            Campo("direccion", "Dirección", obligatorio=True, largo=255),
        ],
        consulta_lista="SELECT * FROM entidad_contratante ORDER BY razon_social",
        columnas_lista=[("ruc_entidad", "RUC"), ("razon_social", "Razón social"),
                        ("direccion", "Dirección")],
    ),
    Entidad(
        tabla="telefono_entidad", titulo="Teléfonos de entidades", singular="Teléfono",
        descripcion="Teléfonos de contacto de la entidad.",
        campos=[
            Campo("ruc_entidad", "Entidad", "referencia", obligatorio=True, clave=True,
                  referencia=REF_ENTIDADES),
            Campo("telefono", "Teléfono", obligatorio=True, clave=True, editable_en_clave=True,
                  largo=15, ayuda="ej. 054-605690"),
        ],
        args_actualizar=["ruc_entidad", "@telefono", "telefono"],
        consulta_lista=("SELECT t.*, e.razon_social AS entidad FROM telefono_entidad t "
                        "JOIN entidad_contratante e USING (ruc_entidad) ORDER BY e.razon_social, t.telefono"),
        columnas_lista=[("ruc_entidad", "RUC"), ("entidad", "Entidad"),
                        ("telefono", "Teléfono")],
    ),

    # ------------------------------------------------------------------
    # Licitación, propuesta y el detalle de la propuesta
    # ------------------------------------------------------------------
    Entidad(
        tabla="licitacion", titulo="Licitaciones", singular="Licitación",
        descripcion="Procesos de contratación que la empresa registra y sigue. Deje el código "
                    "vacío y se generará LIC-AAAA-NNNN.",
        campos=[
            Campo("codigo_licitacion", "Código", clave=True, auto=True, largo=13,
                  ayuda="vacío = se genera automáticamente"),
            Campo("nro_requerimiento", "N.° de requerimiento", obligatorio=True, largo=20),
            Campo("tipo_proceso", "Tipo de proceso", "opcion", obligatorio=True,
                  opciones=TIPOS_PROCESO, por_defecto="CONTRATO MENOR"),
            Campo("objeto", "Objeto", "texto_largo", obligatorio=True, largo=500),
            Campo("dependencia_destino", "Dependencia destino", largo=100),
            Campo("fecha_registro", "Fecha de registro", "fecha", obligatorio=True,
                  por_defecto=date.today),
            Campo("fecha_limite_presentacion", "Fecha límite", "fecha"),
            Campo("estado", "Estado", "opcion", obligatorio=True, opciones=ESTADOS_LICITACION,
                  por_defecto="REGISTRADA"),
            Campo("ruc_entidad", "Entidad contratante", "referencia", obligatorio=True,
                  referencia=REF_ENTIDADES),
        ],
        consulta_lista=("SELECT l.*, e.razon_social AS entidad FROM licitacion l "
                        "JOIN entidad_contratante e USING (ruc_entidad) "
                        "ORDER BY l.codigo_licitacion DESC"),
        columnas_lista=[("codigo_licitacion", "Código"), ("estado", "Estado"),
                        ("entidad", "Entidad"), ("nro_requerimiento", "Req."),
                        ("fecha_limite_presentacion", "Límite"), ("objeto", "Objeto")],
        acciones=[("Cambiar estado…", "cambiar_estado")],
    ),
    Entidad(
        tabla="propuesta_comercial", titulo="Propuestas comerciales", singular="Propuesta",
        descripcion="Oferta económica de cada licitación (una por licitación). Al crearla, la "
                    "licitación pasa a EN PREPARACIÓN; una vez PRESENTADA ya no se modifica. "
                    "Seleccione una propuesta para gestionar sus ítems, armadas de pago y equipos.",
        resumen=("codigo_licitacion",),
        detalles=[
            Detalle("item_propuesta", "Ítems", {"codigo_propuesta": "codigo_propuesta"},
                    ocultar=("codigo_propuesta",)),
            Detalle("armada_pago", "Armadas de pago", {"codigo_propuesta": "codigo_propuesta"},
                    ocultar=("codigo_propuesta",)),
            Detalle("propuesta_maquinaria", "Equipos asignados", {"codigo_propuesta": "codigo_propuesta"},
                    ocultar=("codigo_propuesta", "fecha_emision")),
        ],
        campos=[
            Campo("codigo_propuesta", "Código", clave=True, auto=True, largo=14,
                  ayuda="vacío = se genera automáticamente"),
            Campo("fecha_emision", "Fecha de emisión", "fecha", obligatorio=True, por_defecto=date.today),
            Campo("plazo_ejecucion_dias", "Plazo de ejecución (días)", "entero", obligatorio=True),
            Campo("cumple_tdr", "Cumple los términos de referencia", "booleano", por_defecto=True),
            Campo("codigo_licitacion", "Licitación", "referencia", obligatorio=True,
                  referencia=REF_LICITACIONES),
            Campo("dni_suscriptor", "Suscribe", "referencia", obligatorio=True,
                  referencia=REF_REPRESENTANTES),
            Campo("cci_abono", "Cuenta de abono", "referencia", referencia=REF_CUENTAS),
        ],
        consulta_lista=("SELECT p.*, l.estado AS estado_licitacion, t.precio_total "
                        "FROM propuesta_comercial p "
                        "JOIN licitacion l USING (codigo_licitacion) "
                        "JOIN vw_propuesta_total t ON t.codigo_propuesta = p.codigo_propuesta "
                        "ORDER BY p.codigo_propuesta DESC"),
        columnas_lista=[("codigo_propuesta", "Código"), ("codigo_licitacion", "Licitación"),
                        ("estado_licitacion", "Estado licitación"), ("fecha_emision", "Emisión"),
                        ("plazo_ejecucion_dias", "Plazo (días)"), ("precio_total", "Total S/"),
                        ("cumple_tdr", "Cumple TDR"), ("dni_suscriptor", "Suscribe (DNI)"),
                        ("cci_abono", "CCI de abono")],
    ),
    Entidad(
        tabla="item_propuesta", titulo="Ítems de propuesta", singular="Ítem",
        descripcion="Servicio, cantidad y precio. Deje el N.° vacío y se asigna el siguiente.",
        campos=[
            Campo("codigo_propuesta", "Propuesta", "referencia", obligatorio=True, clave=True,
                  referencia=REF_PROPUESTAS),
            Campo("nro_item", "N.° de ítem", "entero", clave=True, auto=True,
                  ayuda="vacío = siguiente número"),
            Campo("descripcion", "Descripción", "texto_largo", obligatorio=True, largo=500),
            Campo("unidad_medida", "Unidad", "opcion", obligatorio=True, opciones=UNIDADES_MEDIDA),
            Campo("cantidad", "Cantidad", "decimal", obligatorio=True),
            Campo("precio_unitario", "Precio unitario (S/)", "decimal", obligatorio=True),
        ],
        consulta_lista=("SELECT i.*, (i.cantidad * i.precio_unitario)::numeric(12,2) AS subtotal "
                        "FROM item_propuesta i ORDER BY i.codigo_propuesta DESC, i.nro_item"),
        columnas_lista=[("codigo_propuesta", "Propuesta"), ("nro_item", "Ítem"),
                        ("descripcion", "Descripción"), ("unidad_medida", "Unidad"),
                        ("cantidad", "Cantidad"), ("precio_unitario", "P. unitario"),
                        ("subtotal", "Subtotal")],
    ),
    Entidad(
        tabla="armada_pago", titulo="Armadas de pago", singular="Armada de pago",
        descripcion="Cuotas de pago. Deje el N.° vacío y se asigna el siguiente.",
        campos=[
            Campo("codigo_propuesta", "Propuesta", "referencia", obligatorio=True, clave=True,
                  referencia=REF_PROPUESTAS),
            Campo("nro_armada", "N.° de armada", "entero", clave=True, auto=True,
                  ayuda="vacío = siguiente número"),
            Campo("dias_plazo", "A los (días)", "entero", obligatorio=True),
            Campo("condicion", "Condición", obligatorio=True, largo=200),
        ],
        consulta_lista="SELECT * FROM armada_pago ORDER BY codigo_propuesta DESC, nro_armada",
        columnas_lista=[("codigo_propuesta", "Propuesta"), ("nro_armada", "Armada"),
                        ("dias_plazo", "Días"), ("condicion", "Condición")],
    ),
    Entidad(
        tabla="propuesta_maquinaria", titulo="Equipos por propuesta", singular="Equipo asignado",
        descripcion="Solo se aceptan equipos con certificado vigente a la fecha de emisión (RA2).",
        campos=[
            Campo("codigo_propuesta", "Propuesta", "referencia", obligatorio=True, clave=True,
                  referencia=REF_PROPUESTAS),
            Campo("placa", "Equipo", "referencia", obligatorio=True, clave=True,
                  editable_en_clave=True, referencia=REF_PLACAS),
        ],
        args_actualizar=["codigo_propuesta", "@placa", "placa"],
        consulta_lista=("SELECT pm.*, m.marca || ' ' || m.modelo AS equipo, p.fecha_emision "
                        "FROM propuesta_maquinaria pm "
                        "JOIN maquinaria m USING (placa) "
                        "JOIN propuesta_comercial p USING (codigo_propuesta) "
                        "ORDER BY pm.codigo_propuesta DESC, pm.placa"),
        columnas_lista=[("codigo_propuesta", "Propuesta"), ("fecha_emision", "Emisión"),
                        ("placa", "Placa"), ("equipo", "Equipo")],
    ),
]

#: Acceso rápido por nombre de tabla.
POR_TABLA = {e.tabla: e for e in ENTIDADES}
