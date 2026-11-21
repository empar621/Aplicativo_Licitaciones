"""Pantalla de mantenimiento genérica de una tabla del catálogo.

Componentes:
    PanelRegistros   lista de una tabla con sus botones:
                         Nuevo      -> formulario vacío     -> CALL sp_<tabla>_insertar(...)
                         Modificar  -> formulario con datos -> CALL sp_<tabla>_actualizar(...)
                         Eliminar   -> confirmación         -> CALL sp_<tabla>_eliminar(clave)
    PanelDetalle     pestañas con las tablas dependientes del registro elegido
                     (cada pestaña es otro PanelRegistros, filtrado por ese registro)
    PantallaEntidad  título + PanelRegistros principal + PanelDetalle (si la tabla
                     tiene tablas dependientes en el catálogo)

Los triggers de la base validan cada operación y registran la bitácora.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from .. import errores
from ..catalogo import ESTADOS_LICITACION, POR_TABLA
from . import estilo, formato
from .formulario import Formulario
from .tabla import TablaDatos


def describir(entidad, fila: dict) -> str:
    """Texto corto que identifica un registro: su clave y, si hay, su resumen."""
    clave = " / ".join(formato.a_texto(fila.get(c)) for c in entidad.claves)
    resumen = " ".join(formato.a_texto(fila.get(c)) for c in entidad.resumen if fila.get(c) is not None)
    return f"{clave}  ·  {resumen}" if resumen else clave


class PanelRegistros(ttk.Frame):
    """Lista de registros de una entidad con los botones para administrarla."""

    def __init__(self, padre, entidad, db, informar, *, detalle=None, al_seleccionar=None,
                 al_cambiar=None, al_cargar=None, filas_visibles=10, elegir_primera=False):
        """
        detalle         objeto Detalle si el panel muestra una tabla dependiente
        al_seleccionar  función sin argumentos: cambió el registro seleccionado
        al_cambiar      función sin argumentos: se insertó, modificó o eliminó algo
        al_cargar       función(cantidad): se volvió a leer la lista
        elegir_primera  seleccionar la primera fila si no hay ninguna elegida
        """
        super().__init__(padre)
        self.entidad = entidad
        self.db = db
        self.informar = informar          # escribe en la barra de estado
        self.detalle = detalle
        self.al_seleccionar = al_seleccionar
        self.al_cambiar = al_cambiar
        self.al_cargar = al_cargar
        self.elegir_primera = elegir_primera
        self.fijos = None                 # {campo: valor} del registro principal (solo detalle)

        barra = ttk.Frame(self)
        barra.pack(fill="x", pady=(0, 8))
        # Un solo botón resaltado por pantalla: el «Nuevo» de la lista principal
        estilo_nuevo = "Accion.TButton" if detalle is None else "TButton"
        self.botones = [
            ttk.Button(barra, text="＋ Nuevo", style=estilo_nuevo, command=self.nuevo),
            ttk.Button(barra, text="✎ Modificar", command=self.modificar),
            ttk.Button(barra, text="🗑 Eliminar", command=self.eliminar),
        ]
        for indice, boton in enumerate(self.botones):
            boton.pack(side="left", padx=(0 if indice == 0 else 6, 0))
        for texto, accion in entidad.acciones:
            boton = ttk.Button(barra, text=texto, command=lambda a=accion: self.ejecutar_accion(a))
            boton.pack(side="left", padx=(12, 0))
            self.botones.append(boton)

        self.buscar = tk.StringVar()
        if detalle is None:               # lista principal: búsqueda y actualización
            ttk.Button(barra, text="⟳ Actualizar", command=self.cargar).pack(side="right")
            self.buscar.trace_add("write", lambda *a: self._filtrar())
            ttk.Entry(barra, textvariable=self.buscar, width=28).pack(side="right", padx=(0, 10))
            ttk.Label(barra, text="Buscar:").pack(side="right", padx=(0, 4))
        else:                             # lista dependiente: una nota de ayuda
            ttk.Label(barra, text=entidad.descripcion, style="Secundario.TLabel").pack(
                side="left", padx=(14, 0))

        ocultas = detalle.ocultar if detalle else ()
        self.tabla = TablaDatos(self, al_doble_clic=self.modificar, al_seleccionar=al_seleccionar,
                                filas_visibles=filas_visibles)
        self.tabla.configurar_columnas([c for c in entidad.columnas_lista if c[0] not in ocultas])
        self.tabla.pack(fill="both", expand=True)
        self.tabla.arbol.bind("<Delete>", lambda e: self.eliminar())

        self.contador = ttk.Label(self, style="Secundario.TLabel")
        if detalle is None:
            self.contador.pack(anchor="w", pady=(6, 0))
        else:
            self._habilitar(False)        # hasta que se elija un registro principal

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    def fijar(self, valores: dict | None):
        """(Solo detalle) Indica de qué registro principal se muestran las filas."""
        self.fijos = valores
        self._habilitar(valores is not None)
        self.cargar()

    def cargar(self, seleccionar: dict | None = None):
        """Lee los registros y los muestra; conserva la fila seleccionada si sigue existiendo."""
        objetivo = seleccionar or self.tabla.seleccion()
        if self.detalle is not None and self.fijos is None:
            filas = []
        else:
            try:
                filas = self.db.consultar_lista(self.entidad.consulta_lista, self.fijos)
            except Exception as error:  # noqa: BLE001
                messagebox.showerror("Error al leer los datos", errores.mensaje(error), parent=self)
                return
        self.tabla.cargar(filas)
        claves = self.entidad.claves
        if objetivo:
            self.tabla.seleccionar(lambda f: all(_igual(f.get(c), objetivo.get(c)) for c in claves))
        self._actualizar_contador()
        self._revisar_seleccion()
        if self.al_cargar:
            self.al_cargar(len(filas))

    def _filtrar(self):
        self.tabla.filtrar(self.buscar.get())
        self._actualizar_contador()
        self._revisar_seleccion()

    def _revisar_seleccion(self):
        """Tras redibujar la lista: elige la primera fila si hace falta y avisa del cambio.

        Tk no emite el aviso de selección cuando la fila elegida desaparece
        (por un filtro o una eliminación), así que se avisa aquí.
        """
        if self.elegir_primera and self.tabla.seleccion() is None:
            self.tabla.seleccionar_primera()
        if self.al_seleccionar:
            self.al_seleccionar()

    def _actualizar_contador(self):
        total, visibles = len(self.tabla.filas), self.tabla.cantidad_visible
        texto = f"{total} registros" if total == visibles else f"{visibles} de {total} registros"
        self.contador.configure(text=texto)

    def _habilitar(self, si: bool):
        for boton in self.botones:
            boton.state(["!disabled"] if si else ["disabled"])

    def _seleccion_obligatoria(self) -> dict | None:
        fila = self.tabla.seleccion()
        if fila is None:
            messagebox.showinfo(self.entidad.titulo, "Primero seleccione un registro de la lista.",
                                parent=self)
        return fila

    def _describir(self, fila: dict) -> str:
        return " / ".join(formato.a_texto(fila.get(c)) for c in self.entidad.claves)

    def _notificar_cambio(self):
        if self.al_cambiar:
            self.al_cambiar()

    # ------------------------------------------------------------------
    # Operaciones (cada una llama a un procedimiento almacenado)
    # ------------------------------------------------------------------
    def nuevo(self):
        def guardar(valores):
            generados = self.db.llamar(self.entidad.proc_insertar,
                                       self.entidad.argumentos_insertar(valores))
            valores.update(generados)  # códigos o números asignados por los triggers
            self.informar(f"Registro guardado: {self.entidad.singular} {self._describir(valores)}")
            self.cargar(seleccionar=valores)
            self._notificar_cambio()

        Formulario(self, self.entidad, self.db, guardar, fijos=self.fijos)

    def modificar(self):
        original = self._seleccion_obligatoria()
        if original is None:
            return

        def guardar(valores):
            self.db.llamar(self.entidad.proc_actualizar,
                           self.entidad.argumentos_actualizar(valores, original))
            self.informar(f"Cambios guardados: {self.entidad.singular} {self._describir(valores)}")
            self.cargar(seleccionar=valores)
            self._notificar_cambio()

        Formulario(self, self.entidad, self.db, guardar, original=original, fijos=self.fijos)

    def eliminar(self):
        fila = self._seleccion_obligatoria()
        if fila is None:
            return
        detalle = self._describir(fila)
        if not messagebox.askyesno("Confirmar eliminación",
                                   f"¿Eliminar {self.entidad.singular.lower()} «{detalle}»?\n\n"
                                   "Esta acción no se puede deshacer.", icon="warning", parent=self):
            return
        try:
            self.db.llamar(self.entidad.proc_eliminar, self.entidad.argumentos_eliminar(fila))
        except Exception as error:  # noqa: BLE001
            messagebox.showerror("No se pudo eliminar", errores.mensaje(error, "eliminar"), parent=self)
            return
        self.informar(f"Registro eliminado: {self.entidad.singular} {detalle}")
        self.cargar()
        self._notificar_cambio()

    def ejecutar_accion(self, accion: str):
        if accion == "cambiar_estado":
            fila = self._seleccion_obligatoria()
            if fila is not None:
                DialogoEstado(self, self.db, fila, al_terminar=self._estado_cambiado)

    def _estado_cambiado(self, fila, estado):
        self.informar(f"Licitación {fila['codigo_licitacion']}: estado cambiado a {estado}")
        self.cargar(seleccionar=fila)
        self._notificar_cambio()


class PanelDetalle(ttk.Frame):
    """Pestañas con las tablas dependientes del registro principal seleccionado."""

    def __init__(self, padre, entidad, db, informar, al_cambiar):
        super().__init__(padre)
        self.entidad = entidad
        self.titulo = ttk.Label(self, style="Subtitulo.TLabel")
        self.titulo.pack(anchor="w", pady=(10, 6))
        self.cuaderno = ttk.Notebook(self)
        self.cuaderno.pack(fill="both", expand=True)

        self.paneles = []   # [(Detalle, PanelRegistros)]
        for detalle in entidad.detalles:
            marco = ttk.Frame(self.cuaderno, padding=(10, 10, 10, 8))
            panel = PanelRegistros(marco, POR_TABLA[detalle.tabla], db, informar, detalle=detalle,
                                   al_cambiar=al_cambiar, filas_visibles=5)
            panel.al_cargar = lambda n, m=marco, p=panel, d=detalle: self._rotular(m, p, d, n)
            panel.pack(fill="both", expand=True)
            self.cuaderno.add(marco, text=detalle.titulo)
            self.paneles.append((detalle, panel))
        self.mostrar(None)

    def _rotular(self, marco, panel, detalle, cantidad):
        """Pone la cantidad de registros en el rótulo de la pestaña: «Teléfonos (2)»."""
        sufijo = f" ({cantidad})" if panel.fijos is not None else ""
        self.cuaderno.tab(marco, text=f"{detalle.titulo}{sufijo}")

    def mostrar(self, fila: dict | None):
        """Muestra las tablas dependientes de la fila principal (None = ninguna elegida)."""
        if fila is None:
            self.titulo.configure(text="Seleccione un registro de la lista para ver su detalle",
                                  style="Secundario.TLabel")
        else:
            self.titulo.configure(text=f"{self.entidad.singular} {describir(self.entidad, fila)}",
                                  style="Subtitulo.TLabel")
        for detalle, panel in self.paneles:
            if fila is None:
                panel.fijar(None)
            else:
                panel.fijar({hija: _limpio(fila.get(principal))
                             for hija, principal in detalle.enlace.items()})


class PantallaEntidad(ttk.Frame):
    """Pantalla completa de una tabla principal: su lista y, debajo, su detalle."""

    def __init__(self, padre, entidad, db, informar):
        super().__init__(padre, padding=(18, 14, 18, 10))
        self.entidad = entidad
        self.detalle = None
        self._tarea_detalle = None

        ttk.Label(self, text=entidad.titulo, style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(self, text=entidad.descripcion, style="Secundario.TLabel",
                  wraplength=estilo.px(self, 940), justify="left").pack(anchor="w", pady=(0, 10))

        if not entidad.detalles:
            self.principal = PanelRegistros(self, entidad, db, informar)
            self.principal.pack(fill="both", expand=True)
            return

        division = ttk.PanedWindow(self, orient="vertical")
        division.pack(fill="both", expand=True)
        self.principal = PanelRegistros(division, entidad, db, informar, filas_visibles=7,
                                        elegir_primera=True, al_seleccionar=self._programar_detalle,
                                        al_cambiar=self._programar_detalle)
        self.detalle = PanelDetalle(division, entidad, db, informar, al_cambiar=self._detalle_cambiado)
        division.add(self.principal, weight=3)
        division.add(self.detalle, weight=2)

    def cargar(self):
        """Vuelve a leer los datos (se llama al entrar a la pantalla y con F5)."""
        self.principal.cargar()
        self._programar_detalle()

    def _programar_detalle(self):
        """Actualiza el detalle una sola vez aunque lleguen varios avisos seguidos."""
        if self.detalle is None:
            return
        if self._tarea_detalle is not None:
            self.after_cancel(self._tarea_detalle)
        self._tarea_detalle = self.after(40, self._mostrar_detalle)

    def _mostrar_detalle(self):
        self._tarea_detalle = None
        self.detalle.mostrar(self.principal.tabla.seleccion())

    def _detalle_cambiado(self):
        """Un cambio en el detalle puede alterar la lista principal (totales, estados)."""
        self.principal.cargar()


class DialogoEstado(tk.Toplevel):
    """Cambia el estado de una licitación con sp_licitacion_cambiar_estado."""

    def __init__(self, padre, db, fila, al_terminar):
        super().__init__(padre)
        self.db, self.fila, self.al_terminar = db, fila, al_terminar
        self.title("Cambiar estado")
        self.configure(background=estilo.FONDO)
        self.transient(padre.winfo_toplevel())
        self.resizable(False, False)

        cuerpo = ttk.Frame(self, padding=18)
        cuerpo.pack(fill="both")
        ttk.Label(cuerpo, text=f"Licitación {fila['codigo_licitacion']}",
                  style="Subtitulo.TLabel").pack(anchor="w")
        ttk.Label(cuerpo, text=f"Estado actual: {fila['estado']}",
                  style="Secundario.TLabel").pack(anchor="w", pady=(0, 10))
        self.estado = tk.StringVar(value=fila["estado"])
        ttk.Combobox(cuerpo, textvariable=self.estado, values=ESTADOS_LICITACION,
                     state="readonly", width=24).pack(anchor="w")
        ttk.Label(cuerpo, wraplength=estilo.px(self, 340), justify="left", style="Ayuda.TLabel",
                  text="Flujo: REGISTRADA → EN PREPARACIÓN → PRESENTADA → ADJUDICADA / "
                       "NO ADJUDICADA. Para presentar se necesita una propuesta (RA5).").pack(
            anchor="w", pady=(8, 0))

        botones = ttk.Frame(cuerpo)
        botones.pack(fill="x", pady=(14, 0))
        ttk.Button(botones, text="Cancelar", command=self.destroy).pack(side="right")
        ttk.Button(botones, text="Cambiar", style="Accion.TButton",
                   command=self.guardar).pack(side="right", padx=(0, 8))
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()

    def guardar(self):
        estado = self.estado.get()
        try:
            self.db.llamar("sp_licitacion_cambiar_estado", [self.fila["codigo_licitacion"], estado])
        except Exception as error:  # noqa: BLE001
            messagebox.showerror("No se pudo cambiar el estado", errores.mensaje(error), parent=self)
            return
        self.destroy()
        self.al_terminar(self.fila, estado)


def _limpio(valor):
    """Quita los espacios de relleno de las columnas char."""
    return valor.strip() if isinstance(valor, str) else valor


def _igual(a, b) -> bool:
    """Compara claves ignorando espacios de relleno (columnas char)."""
    if isinstance(a, str) and isinstance(b, str):
        return a.strip().upper() == b.strip().upper()
    return a == b
