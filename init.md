### Cómo trabajar a partir de ahora
Para desarrollar el frontend, necesitarás tener una terminal abierta ejecutando el modo "watch" para que tus cambios en SCSS se reflejen automáticamente:

```
npm run watch
```
Y en otra terminal (dentro del entorno virtual), ejecutas tu servidor Flask normalmente:

```
python app.py
```

Para ejecutar Huey, necesitarás tener otra terminal abierta ejecutando (dentro del entorno virtual):

```
python -m huey.bin.huey_consumer run_huey.huey
```