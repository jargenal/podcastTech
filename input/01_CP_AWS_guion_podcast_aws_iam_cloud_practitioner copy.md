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