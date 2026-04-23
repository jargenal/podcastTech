[TITULO]
[EN]AWS IAM para Cloud Practitioner[/EN]: guía de estudio rigurosa y orientada al examen

[IDIOMA]
es_latam

[VOZ]
default_es_mx.wav

[TEXTO]
Bienvenidos.
Hoy vamos a estudiar a profundidad [EN]AWS Identity and Access Management[/EN], o [EN]IAM[/EN].
Este episodio está diseñado como una guía de preparación rigurosa para la certificación [EN]AWS Certified Cloud Practitioner[/EN].
La meta no es solo memorizar definiciones.
La meta es entender cómo piensa [EN]AWS[/EN] sobre identidad, autenticación, autorización y seguridad básica en la nube.
Porque en el examen, [EN]IAM[/EN] aparece de manera directa.
Pero también aparece de manera indirecta.
Aparece cuando te preguntan por seguridad.
Por acceso a servicios.
Por buenas prácticas.
Por uso de la cuenta root.
Por acceso entre cuentas.
Y por cómo dar permisos correctos sin dar más de lo necesario.

[PAUSA]
900

[TEXTO]
Empecemos con la idea central.
[EN]IAM[/EN] es el servicio que permite controlar quién puede entrar a AWS y qué puede hacer dentro de AWS.
Dicho de otra forma.
[EN]IAM[/EN] administra identidades y permisos.
En lenguaje de examen, recuerda esta distinción.
Autenticación responde a la pregunta: quién eres.
Autorización responde a la pregunta: qué puedes hacer.
[EN]IAM[/EN] participa en ambas.
Ayuda a verificar identidades y ayuda a decidir permisos.
Esta es una de las bases del modelo de seguridad en AWS.

[PAUSA]
900

[TEXTO]
Ahora bien.
Para [EN]Cloud Practitioner[/EN], hay algo muy importante.
No necesitas llegar al nivel profundo de un ingeniero de seguridad.
Pero sí necesitas comprender bien los componentes fundamentales.
Usuarios.
Grupos.
Roles.
Políticas.
[EN]MFA[/EN] o autenticación multifactor.
Cuenta root.
Acceso temporal.
Principio de menor privilegio.
Y la diferencia entre [EN]IAM[/EN] e [EN]IAM Identity Center[/EN].
Todo eso suele mezclarse en preguntas con trampas sutiles.

[PAUSA]
900

[TEXTO]
Vamos entonces por partes.
Primero, la cuenta root.
La cuenta root no es lo mismo que un usuario [EN]IAM[/EN].
La cuenta root es la identidad principal creada cuando nace una cuenta de AWS.
Tiene control total sobre todos los recursos y servicios de esa cuenta.
Por eso mismo, es la identidad más sensible.
En examen, cuando veas root, piensa inmediatamente en alto riesgo y uso excepcional.
La buena práctica es proteger la cuenta root con una contraseña fuerte y [EN]multi-factor authentication[/EN].
Y usarla lo menos posible.
[EN]AWS[/EN] insiste en proteger la cuenta root y en evitar su uso cotidiano.
Ese es un mensaje muy repetido en documentación oficial y también en la guía del examen.

[PAUSA]
900

[TEXTO]
Aquí viene una trampa clásica.
Si una pregunta dice que un administrador necesita hacer trabajo diario en AWS, la respuesta no debe ser usar la cuenta root.
La respuesta correcta suele ser crear una identidad con los permisos apropiados.
Puede ser un usuario [EN]IAM[/EN].
O puede ser acceso federado mediante [EN]IAM Identity Center[/EN].
Pero no root para tareas operativas normales.
Root se reserva para tareas muy específicas y poco frecuentes.
Por ejemplo, algunas configuraciones de cuenta de muy alto nivel.
En tu cabeza, root debe sonar a último recurso, no a primera opción.

[PAUSA]
900

[TEXTO]
Pasemos ahora a los usuarios [EN]IAM[/EN].
Un usuario [EN]IAM[/EN] representa una identidad dentro de [EN]AWS[/EN].
Tradicionalmente, un usuario IAM puede tener credenciales de largo plazo.
Por ejemplo, una contraseña para entrar a la consola.
Y también [EN]access keys[/EN] para usar [EN]CLI[/EN] o [EN]APIs[/EN].
Pero aquí debes actualizar tu mentalidad a la visión moderna de AWS.
[EN]AWS[/EN] recomienda cada vez más usar roles y credenciales temporales en lugar de usuarios [EN]IAM[/EN] con credenciales permanentes, especialmente para humanos y cargas de trabajo.
Esto es muy importante para examen.
Que un recurso exista, no significa que sea la opción preferida.
[EN]IAM users[/EN] existen.
Pero no siempre son la recomendación principal.

[PAUSA]
900
