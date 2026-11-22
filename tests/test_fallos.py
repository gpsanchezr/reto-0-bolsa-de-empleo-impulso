import inspect


def test_arquitectura_modular_servicios():
    import servicios

    funciones_negocio = [
        nombre
        for nombre, objeto in inspect.getmembers(servicios, inspect.isfunction)
        if objeto.__module__ == servicios.__name__ and not nombre.startswith("_")
    ]
    modelos = [
        nombre
        for nombre, objeto in inspect.getmembers(servicios, inspect.isclass)
        if objeto.__module__ == servicios.__name__ and not nombre.startswith("_")
    ]

    assert funciones_negocio or modelos, (
        "servicios debe definir funciones de negocio o modelos propios."
    )
