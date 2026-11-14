# Voces grabadas del modo jugador

Pon aquí archivos MP3 con estos nombres y el juego los reproduce en el momento justo:

| Archivo | Cuándo suena | Ejemplo de frase |
|---|---|---|
| `bienvenido.mp3` | Al aterrizar | «¡Llegamos! ¡A salvar este lugar!» |
| `ayuda.mp3` | Cuando estalla un evento | «¡Ayuda! ¡Ayuda, por favor!» |
| `vamos-a-salir.mp3` | Después de la alerta | «¡Tranquilos! ¡Vamos a salir de esto!» |
| `gracias.mp3` | Al ayudar a un vecino | «¡Gracias, héroe!» |
| `necesito-ayuda.mp3` | Al acercarte a un vecino en peligro | «¡Hoy necesito ayuda, por favor!» |
| `hola-heroe.mp3` | Al acercarte a un vecino que te espera | «¡Hola! ¡Tengo una misión para ti!» |
| `lo-logramos.mp3` | Al terminar la operación | «¡Lo logramos! ¡Estamos a salvo!» |

Grábalos con el celular (voz fuerte y con emoción), conviértelos a MP3 y cópialos con estos nombres exactos.

## Paso obligatorio: anotar el archivo en `voces.json`

El juego solo pide las voces que figuran en `voces.json` (el manifiesto de esta carpeta). Quien agregue una voz debe
sumar ahí el nombre exacto de su archivo; si no figura, el juego no la busca y no suena. Hoy el manifiesto está vacío
(`[]`) porque todavía no hay ninguna voz grabada. Con dos voces quedaría así:

```json
["gracias.mp3", "lo-logramos.mp3"]
```

- Si se borra un archivo, hay que quitarlo también del manifiesto (si no, el navegador lo pide y da error 404).
- El manifiesto se lee una vez por sesión: después de cambiarlo, recarga la página.
- Si un archivo falta, el juego sigue sin esa voz.

## El botón «Voces» del juego

- Sin voces en el manifiesto dice «Voces: no». Si la persona lo activa, habla la voz sintetizada del navegador.
- Con voces en el manifiesto dice «Voces: sí» y suenan las grabadas; la voz sintetizada ya no se usa, para que no
  suenen las dos a la vez. En «Voces: no» no suena ninguna.
