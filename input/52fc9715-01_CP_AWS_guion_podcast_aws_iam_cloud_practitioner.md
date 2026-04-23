[TITULO]
AWS IAM para Cloud Practitioner: guía de estudio rigurosa y orientada al examen

[IDIOMA]
es_latam

[VOZ]
default_es_mx.wav

[TEXTO]
Bienvenidos.

Hoy vamos a estudiar a profundidad [EN]AWS Identity and Access Management[/EN], o IAM.

Este episodio está diseñado como una guía de preparación rigurosa para la certificación [EN]AWS Certified Cloud Practitioner[/EN].

La meta no es solo memorizar definiciones.

La meta es entender cómo piensa AWS sobre identidad, autenticación, autorización y seguridad básica en la nube.

Porque en el examen, IAM aparece de manera directa.

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

IAM es el servicio que permite controlar quién puede entrar a AWS y qué puede hacer dentro de AWS.

Dicho de otra forma.

IAM administra identidades y permisos.

En lenguaje de examen, recuerda esta distinción.

Autenticación responde a la pregunta: quién eres.

Autorización responde a la pregunta: qué puedes hacer.

IAM participa en ambas.

Ayuda a verificar identidades y ayuda a decidir permisos.

Esta es una de las bases del modelo de seguridad en AWS.

[PAUSA]
900

[TEXTO]
Ahora bien.

Para Cloud Practitioner, hay algo muy importante.

No necesitas llegar al nivel profundo de un ingeniero de seguridad.

Pero sí necesitas comprender bien los componentes fundamentales.

Usuarios.

Grupos.

Roles.

Políticas.

[MFA] o autenticación multifactor.

Cuenta root.

Acceso temporal.

Principio de menor privilegio.

Y la diferencia entre IAM e [EN]IAM Identity Center[/EN].

Todo eso suele mezclarse en preguntas con trampas sutiles.

[PAUSA]
900

[TEXTO]
Vamos entonces por partes.

Primero, la cuenta root.

La cuenta root no es lo mismo que un usuario IAM.

La cuenta root es la identidad principal creada cuando nace una cuenta de AWS.

Tiene control total sobre todos los recursos y servicios de esa cuenta.

Por eso mismo, es la identidad más sensible.

En examen, cuando veas root, piensa inmediatamente en alto riesgo y uso excepcional.

La buena práctica es proteger la cuenta root con una contraseña fuerte y [EN]multi-factor authentication[/EN].

Y usarla lo menos posible.

AWS insiste en proteger la cuenta root y en evitar su uso cotidiano.

Ese es un mensaje muy repetido en documentación oficial y también en la guía del examen.

[PAUSA]
900

[TEXTO]
Aquí viene una trampa clásica.

Si una pregunta dice que un administrador necesita hacer trabajo diario en AWS, la respuesta no debe ser usar la cuenta root.

La respuesta correcta suele ser crear una identidad con los permisos apropiados.

Puede ser un usuario IAM.

O puede ser acceso federado mediante [EN]IAM Identity Center[/EN].

Pero no root para tareas operativas normales.

Root se reserva para tareas muy específicas y poco frecuentes.

Por ejemplo, algunas configuraciones de cuenta de muy alto nivel.

En tu cabeza, root debe sonar a último recurso, no a primera opción.

[PAUSA]
900

[TEXTO]
Pasemos ahora a los usuarios IAM.

Un usuario IAM representa una identidad dentro de AWS.

Tradicionalmente, un usuario IAM puede tener credenciales de largo plazo.

Por ejemplo, una contraseña para entrar a la consola.

Y también [EN]access keys[/EN] para usar CLI o APIs.

Pero aquí debes actualizar tu mentalidad a la visión moderna de AWS.

AWS recomienda cada vez más usar roles y credenciales temporales en lugar de usuarios IAM con credenciales permanentes, especialmente para humanos y cargas de trabajo.

Esto es muy importante para examen.

Que un recurso exista, no significa que sea la opción preferida.

IAM users existen.

Pero no siempre son la recomendación principal.

[PAUSA]
900

[TEXTO]
Entonces.

¿Cuándo aparecen los usuarios IAM en preguntas?

Aparecen cuando se habla de acceso individual dentro de una sola cuenta.

Cuando se quiere dar acceso a la consola a una persona específica.

Cuando se manejan [EN]access keys[/EN].

O cuando se habla de agrupar permisos por medio de grupos.

Pero si la pregunta habla de reducir riesgo, evitar credenciales permanentes o dar acceso temporal, probablemente la respuesta correcta se mueva hacia roles, federación o [EN]IAM Identity Center[/EN].

[PAUSA]
900

[TEXTO]
Ahora hablemos de grupos.

Un grupo IAM es una colección de usuarios IAM.

Sirve para asignar permisos a varios usuarios de una sola vez.

Si diez administradores necesitan permisos similares, puedes ponerlos en un grupo y asociar permisos al grupo.

Eso simplifica la administración.

Hay una idea clave aquí.

Los grupos contienen usuarios.

Los grupos no contienen roles.

Y un grupo no es una credencial por sí mismo.

Es simplemente un mecanismo de organización para permisos.

Otra trampa frecuente de examen es confundir grupo con rol.

No son lo mismo.

Grupo es para organizar usuarios IAM.

Rol es una identidad asumible, usualmente temporal.

[PAUSA]
900

[TEXTO]
Llegamos a los roles.

Este es uno de los conceptos más importantes de IAM.

Un rol IAM es una identidad que no está asociada permanentemente a una persona específica como un usuario tradicional.

En cambio, se asume cuando se necesita.

Cuando una entidad asume un rol, recibe credenciales temporales.

Y esto es extremadamente valioso desde el punto de vista de seguridad.

Porque reduce el uso de credenciales de largo plazo.

En AWS, muchas arquitecturas seguras giran alrededor de roles.

[PAUSA]
900

[TEXTO]
¿Quién puede asumir un rol?

Muchas entidades.

Un usuario IAM.

Una aplicación.

Un servicio de AWS.

Una instancia EC2.

Una función Lambda.

Un usuario federado.

Incluso una entidad en otra cuenta de AWS.

Por eso, cuando en examen te hablan de acceso entre cuentas, o de permitir que un servicio haga acciones en tu nombre, piensa primero en roles.

Por ejemplo.

Si una instancia EC2 necesita leer objetos en un bucket S3, la práctica recomendada no es guardar [EN]access keys[/EN] dentro del servidor.

La práctica recomendada es asociar un rol a la instancia.

Ese patrón aparece muchísimo en preguntas de seguridad.

[PAUSA]
900

[TEXTO]
Quiero detenerme aquí porque este punto es decisivo.

Una pregunta de examen puede decirte que una aplicación que corre en EC2 necesita acceder a DynamoDB o S3.

Y te dará varias opciones.

Una mala opción será crear un usuario IAM, generar claves, copiarlas al servidor y guardarlas en un archivo.

La mejor opción normalmente será usar un rol IAM para EC2.

¿Por qué?

Porque el rol entrega credenciales temporales y AWS las administra de forma más segura.

Ese razonamiento debes tenerlo muy claro.

[PAUSA]
900

[TEXTO]
Vamos ahora a las políticas.

Las políticas son el corazón de la autorización en IAM.

Una política define permisos.

Normalmente se expresa en formato JSON.

En una política se especifica qué acciones están permitidas o denegadas, sobre qué recursos y, a veces, bajo qué condiciones.

El examen no suele pedirte escribir JSON completo.

Pero sí puede presentarte fragmentos o conceptos.

Debes saber que las políticas controlan acciones como [EN]s3:GetObject[/EN], [EN]ec2:StartInstances[/EN] o [EN]dynamodb:PutItem[/EN].

Y que también señalan recursos concretos o usan comodines.

[PAUSA]
900

[TEXTO]
Hay varios tipos de políticas que debes distinguir a nivel conceptual.

Primero, las políticas administradas por AWS.

Estas son creadas y mantenidas por AWS.

Son reutilizables y convenientes.

Segundo, las políticas administradas por el cliente.

Estas las crea tu organización en tu cuenta.

Sirven cuando necesitas control más específico.

Tercero, las políticas en línea, o [EN]inline policies[/EN].

Van incrustadas directamente en un usuario, grupo o rol específico.

Para Cloud Practitioner, lo más importante es entender que las políticas administradas son reutilizables, mientras que una inline suele quedar atada a una sola identidad.

[PAUSA]
900

[TEXTO]
Ahora vamos a una regla crítica de examen.

En IAM, una denegación explícita gana sobre una autorización.

Repito.

Si una política permite algo, pero otra política lo deniega explícitamente, el resultado final es denegado.

Además, por defecto, todo empieza en denegado implícito.

Eso significa que si no hay una autorización explícita, la acción no se permite.

Este modelo mental te ayuda a resolver preguntas confusas.

Estado inicial.

Denegado implícito.

Si aparece un [EN]Allow[/EN], puede permitirse.

Pero si aparece un [EN]Deny[/EN] explícito, gana el [EN]Deny[/EN].

[PAUSA]
900

[TEXTO]
Ahora pensemos en el principio de menor privilegio.

Este es uno de los pilares del examen.

Menor privilegio significa otorgar solo los permisos mínimos necesarios para realizar una tarea.

Ni más.

Ni menos.

Si un usuario solo debe leer archivos en un bucket específico, no debe recibir permisos de escritura ni acceso a todos los buckets.

Si una aplicación solo debe consultar una tabla, no debe tener permisos administrativos sobre toda la base de datos.

Menor privilegio reduce superficie de ataque, errores y abuso accidental.

En el examen, casi siempre que veas una opción “más segura”, “más recomendada” o “alineada a buenas prácticas”, piensa si aplica menor privilegio.

[PAUSA]
900

[TEXTO]
Conectemos esto con un ejemplo.

Supón que una empresa tiene un desarrollador que solo necesita ver logs en CloudWatch.

¿Qué sería incorrecto?

Darle [EN]AdministratorAccess[/EN].

¿Por qué?

Porque eso rompe el principio de menor privilegio.

La opción correcta sería asignar una política mucho más específica.

Tal vez una administrada por AWS que solo permita lectura de logs.

O una política personalizada más precisa.

Este tipo de comparación entre permiso amplio y permiso mínimo es muy común.

[PAUSA]
900

[TEXTO]
Hablemos ahora de MFA.

[MFA], [EN]multi-factor authentication[/EN], agrega una capa adicional al proceso de autenticación.

No basta con saber la contraseña.

También debes demostrar posesión de otro factor.

Por ejemplo, una aplicación autenticadora o una llave física compatible.

AWS recomienda habilitar MFA especialmente para la cuenta root, y también para identidades humanas sensibles.

En examen, si te preguntan cómo aumentar la seguridad del inicio de sesión con bajo esfuerzo, MFA suele ser una respuesta muy fuerte.

[PAUSA]
900

[TEXTO]
Una trampa frecuente es creer que MFA reemplaza a los permisos.

No.

MFA fortalece la autenticación.

No sustituye políticas IAM.

Un usuario con MFA sigue necesitando permisos apropiados.

Y un usuario con demasiados permisos sigue siendo riesgoso aunque use MFA.

Dicho simple.

MFA ayuda a verificar mejor quién entra.

IAM policies deciden qué puede hacer una vez dentro.

[PAUSA]
900

[TEXTO]
Pasemos a las credenciales.

Hay dos mundos que debes separar mentalmente.

Credenciales de largo plazo.

Y credenciales temporales.

Las de largo plazo suelen asociarse a usuarios IAM.

Como contraseñas o [EN]access keys[/EN] estables.

Las temporales suelen llegar por medio de roles o sesiones federadas.

AWS favorece fuertemente el uso de credenciales temporales cuando sea posible.

¿Por qué?

Porque expiran.

Y si una credencial temporal se filtra, el tiempo de exposición es menor.

Este principio aparece una y otra vez en prácticas modernas de seguridad.

[PAUSA]
900

[TEXTO]
Cuando escuches el término [EN]STS[/EN], [EN]Security Token Service[/EN], piensa en esto.

STS emite credenciales temporales.

No necesitas profundizar demasiado para Cloud Practitioner.

Pero sí debes saber que está detrás de muchas situaciones en las que un rol es asumido y genera acceso temporal.

Si el examen te habla de acceso temporal, entre cuentas o federado, STS puede estar en el trasfondo conceptual.

[PAUSA]
900

[TEXTO]
Ahora hablemos de acceso programático.

Acceso programático significa acceso desde herramientas, código, scripts, SDKs o CLI.

Tradicionalmente, esto podía hacerse con [EN]access keys[/EN] de un usuario IAM.

Pero otra vez aparece la buena práctica moderna.

Siempre que se pueda, usa roles y credenciales temporales.

No embebas claves en el código.

No subas claves a repositorios.

No pongas secretos en texto plano en archivos de configuración.

En examen, una opción que implique claves hardcodeadas suele ser una mala señal.

[PAUSA]
900

[TEXTO]
Aquí se conecta otro tema importante.

Gestión de secretos.

Aunque el foco de este episodio es IAM, el examen puede relacionar IAM con servicios como [EN]AWS Secrets Manager[/EN] o [EN]Systems Manager Parameter Store[/EN].

La idea general es que no debes almacenar credenciales sensibles de forma insegura.

IAM decide permisos.

Pero para almacenar secretos de manera adecuada, AWS ofrece servicios especializados.

Entonces, si una pregunta mezcla “credenciales”, “aplicación” y “almacenamiento seguro”, no siempre la respuesta es solo IAM.

Puede involucrar Secrets Manager más permisos IAM apropiados.

[PAUSA]
900

[TEXTO]
Vamos ahora a la federación.

Este concepto puede sonar complejo al principio, pero para Cloud Practitioner puedes verlo así.

Federación es permitir que usuarios se autentiquen con una identidad externa y luego accedan a AWS sin necesitar necesariamente un usuario IAM tradicional en cada cuenta.

Eso puede conectarse con directorios corporativos o proveedores de identidad.

AWS hoy empuja mucho el uso de [EN]IAM Identity Center[/EN] para acceso de la fuerza laboral.

Y aquí hay que entender bien la diferencia con IAM clásico.

[PAUSA]
900

[TEXTO]
IAM clásico te da componentes como usuarios, grupos, roles y políticas dentro de una cuenta o entre cuentas.

IAM Identity Center, antes conocido como [EN]AWS Single Sign-On[/EN], está orientado a centralizar acceso para usuarios de la organización a múltiples cuentas AWS y también a aplicaciones.

Permite conectar un proveedor de identidad existente, sincronizar usuarios y grupos, y asignar acceso de forma central.

Para el examen, recuerda esta idea.

Si la pregunta habla de muchos usuarios corporativos, múltiples cuentas AWS, acceso centralizado y experiencia de inicio de sesión unificada, piensa en IAM Identity Center.

[PAUSA]
900

[TEXTO]
Quiero reforzar esa comparación.

Usuario IAM.

Más local y tradicional dentro de una cuenta.

IAM Identity Center.

Más centralizado y moderno para gestionar acceso de personas a varias cuentas y aplicaciones.

Rol IAM.

Ideal para acceso temporal, acceso entre cuentas y permisos para servicios o workloads.

Estas tres piezas se parecen, pero cumplen funciones distintas.

El examen puede jugar con esa similitud.

[PAUSA]
900

[TEXTO]
Ahora entremos al acceso entre cuentas.

En AWS, es común que una cuenta necesite permitir cierto acceso a otra cuenta.

Por ejemplo, un equipo central de seguridad que revisa logs o configuraciones en varias cuentas.

La forma típica y segura de hacerlo es mediante roles.

Una cuenta define un rol y establece una política de confianza para que una entidad de otra cuenta pueda asumirlo.

Luego, la política de permisos del rol define qué acciones podrá realizar.

Para nivel examen, lo importante no es memorizar cada detalle técnico.

Lo importante es saber que acceso entre cuentas no significa compartir contraseñas ni replicar usuarios manualmente en todas partes.

Suele resolverse elegantemente con roles.

[PAUSA]
900

[TEXTO]
Acabamos de mencionar un concepto adicional.

La política de confianza.

Esto es útil para distinguir dos planos en un rol.

Uno.

Quién puede asumir el rol.

Dos.

Qué puede hacer el rol una vez asumido.

La primera parte vive en la relación de confianza.

La segunda parte en la política de permisos.

Puede que el examen no lo diga con este nivel de detalle.

Pero tenerlo claro te ayuda a entender preguntas sobre delegación y acceso cruzado.

[PAUSA]
900

[TEXTO]
Hablemos ahora de recursos basados en políticas y de identidades basadas en políticas.

En AWS, algunas políticas se adjuntan a identidades, como usuarios, grupos o roles.

Otras políticas pueden ir en recursos, por ejemplo ciertos buckets S3 o claves KMS.

Para Cloud Practitioner basta con comprender que el acceso final puede depender de más de una capa.

No todo vive únicamente en el usuario.

A veces el recurso también tiene reglas.

Y cuando hay varias políticas interactuando, recuerda la lógica de [EN]Allow[/EN], [EN]Deny[/EN] y denegación implícita.

[PAUSA]
900

[TEXTO]
Ahora vamos con las buenas prácticas de seguridad más importantes alrededor de IAM.

Voy a enumerarlas, pero no como lista seca.

Quiero que las entiendas como criterios de examen.

Primera.

Protege la cuenta root y no la uses para trabajo diario.

Segunda.

Habilita MFA, especialmente en identidades críticas.

Tercera.

Aplica el principio de menor privilegio.

Cuarta.

Prefiere roles y credenciales temporales sobre claves permanentes cuando sea posible.

Quinta.

No compartas credenciales entre personas.

Sexta.

Rota y administra credenciales con cuidado.

Séptima.

Audita y revisa permisos regularmente.

Octava.

Usa mecanismos centralizados para acceso de usuarios humanos cuando la organización crece, como IAM Identity Center.

Estas ideas te servirán tanto en preguntas directas como en escenarios.

[PAUSA]
900

[TEXTO]
Cuando digo revisar permisos, entran otros servicios y capacidades complementarias.

Por ejemplo, [EN]IAM Access Analyzer[/EN].

A nivel muy general, Access Analyzer ayuda a identificar accesos amplios o externos a recursos.

No necesitas ser experto en él para Cloud Practitioner.

Pero sí conviene reconocer que existe como herramienta para analizar permisos y accesibilidad.

Si una pregunta habla de identificar recursos compartidos externamente o validar exposición de acceso, Access Analyzer puede aparecer como respuesta plausible.

[PAUSA]
900

[TEXTO]
También es útil mencionar [EN]CloudTrail[/EN], aunque no es parte de IAM como tal.

CloudTrail registra actividad de la cuenta y llamadas API.

Esto es importante porque seguridad no es solo dar permisos.

También es registrar quién hizo qué.

Entonces, si una pregunta mezcla auditoría, rastreo de acciones e identidad, la combinación conceptual suele ser IAM para permisos y CloudTrail para trazabilidad.

No confundas ambos roles.

IAM controla acceso.

CloudTrail registra actividad.

[PAUSA]
900

[TEXTO]
Otra confusión común en examen es entre autenticación humana y permisos para servicios.

Ejemplo.

Un empleado entra al [EN]AWS Management Console[/EN].

Eso es acceso humano.

Puede involucrar IAM user, federación o IAM Identity Center.

Ahora piensa en una función Lambda que necesita escribir logs o leer un secreto.

Eso es permiso para un workload o servicio.

Ahí hablamos de roles de ejecución y políticas IAM.

Si la pregunta describe una aplicación, un servicio administrado o una máquina virtual haciendo acciones automáticas, piensa en roles para servicios, no en usuarios humanos.

[PAUSA]
900

[TEXTO]
Vamos con varios escenarios tipo examen.

Escenario uno.

Una empresa quiere que sus empleados entren a varias cuentas AWS con un solo inicio de sesión y manejo centralizado.

La respuesta más alineada será IAM Identity Center.

Escenario dos.

Una aplicación en EC2 necesita leer archivos de un bucket S3.

La respuesta más segura será asignar un rol a la instancia EC2.

Escenario tres.

Se desea aumentar la seguridad del administrador principal de la cuenta.

La respuesta fuerte será habilitar MFA para la cuenta root y evitar su uso diario.

Escenario cuatro.

Un desarrollador necesita únicamente ver métricas y logs.

La respuesta correcta debe respetar menor privilegio, no dar administrador total.

Escenario cinco.

Una empresa quiere permitir que una cuenta AWS secundaria acceda a ciertos recursos de una cuenta central.

La respuesta suele girar alrededor de un rol entre cuentas.

[PAUSA]
900

[TEXTO]
Vamos a profundizar ahora en los errores típicos que debes evitar en el examen.

Error uno.

Pensar que IAM sirve solo para la consola web.

No.

IAM también controla acceso programático a APIs y herramientas.

Error dos.

Pensar que grupos e IAM roles son equivalentes.

No.

Grupo organiza usuarios.

Rol se asume para obtener permisos temporales.

Error tres.

Pensar que root es el usuario administrador recomendado para operar.

No.

Es la identidad más poderosa, pero no la recomendada para tareas cotidianas.

Error cuatro.

Pensar que MFA reemplaza políticas de permisos.

No.

Refuerza autenticación, no autorización.

Error cinco.

Pensar que la opción más amplia en permisos es la mejor porque “evita errores de acceso”.

En seguridad AWS, eso casi siempre es mala práctica.

[PAUSA]
900

[TEXTO]
Error seis.

Confundir IAM con Organizations.

AWS Organizations sirve para gobernanza y administración de múltiples cuentas.

IAM sirve para identidades y permisos.

Pueden trabajar juntos.

Pero no son lo mismo.

Error siete.

Confundir IAM con Cognito.

IAM está enfocado en acceso a recursos AWS y administración de identidades dentro del entorno de AWS.

Amazon Cognito está más orientado a autenticación y gestión de usuarios finales en aplicaciones.

En Cloud Practitioner esta diferencia puede aparecer de forma básica.

Si la pregunta habla de usuarios finales de una app web o móvil, Cognito puede ser más apropiado.

Si habla de administrar acceso a recursos AWS, IAM es la referencia principal.

[PAUSA]
900

[TEXTO]
Ahora hagamos un mapa mental rápido de decisión.

Si la pregunta dice “proteger la cuenta principal”.

Piensa en root más MFA y uso limitado.

Si dice “dar permisos a una persona dentro de AWS”.

Piensa en IAM user o acceso federado, según el contexto.

Si dice “dar permisos a varios usuarios similares”.

Piensa en grupo IAM.

Si dice “dar acceso temporal o a un servicio AWS”.

Piensa en rol.

Si dice “centralizar acceso a múltiples cuentas y aplicaciones para empleados”.

Piensa en IAM Identity Center.

Si dice “dar solo lo necesario”.

Piensa en menor privilegio.

Si dice “fortalecer inicio de sesión”.

Piensa en MFA.

Si dice “no quiero claves permanentes embebidas”.

Piensa en roles y credenciales temporales.

[PAUSA]
900

[TEXTO]
Hablemos brevemente de políticas basadas en identidad y políticas basadas en recurso desde una óptica práctica.

Imagina que quieres permitir a un rol leer un bucket S3.

Puedes adjuntar permisos al rol.

Eso es una política basada en identidad.

Pero también podrías tener una política en el bucket que permita acceso a cierta entidad.

Eso sería una política basada en recurso.

Para el examen no necesitas volverte experto en cada combinación.

Lo importante es saber que en AWS los permisos pueden venir desde diferentes lados.

Y la evaluación final considera todas esas piezas.

[PAUSA]
900

[TEXTO]
Ahora, un punto sutil pero muy útil.

“Quién puede iniciar sesión” no siempre es igual a “quién puede llamar APIs”.

Por ejemplo, un usuario puede tener acceso a la consola, pero no necesariamente permisos para crear instancias.

Y una aplicación puede tener permisos para usar S3 sin que exista una persona entrando con usuario y contraseña.

Esta separación entre identidad humana y entidad de software es clave para interpretar escenarios.

[PAUSA]
900

[TEXTO]
Vamos a dedicar un segmento a preguntas tramposas de verdadero o falso en tu mente.

Primera afirmación.

La cuenta root debe usarse para tareas administrativas diarias porque tiene todos los permisos.

Falso.

Segunda afirmación.

MFA mejora la seguridad del inicio de sesión.

Verdadero.

Tercera afirmación.

Un rol IAM suele usarse para otorgar acceso temporal.

Verdadero.

Cuarta afirmación.

Un grupo IAM es la mejor forma de dar acceso temporal entre cuentas.

Falso.

Quinta afirmación.

El principio de menor privilegio consiste en otorgar permisos amplios para evitar fallos operativos.

Falso.

Sexta afirmación.

IAM Identity Center ayuda a centralizar acceso a cuentas AWS y aplicaciones.

Verdadero.

Séptima afirmación.

Una denegación explícita puede anular una autorización.

Verdadero.

[PAUSA]
900

[TEXTO]
Ahora, una mini sección de vocabulario esencial para memorizar bien.

[EN]Principal[/EN].

Entidad que hace una solicitud a AWS.

Puede ser usuario, rol u otra identidad.

[EN]Policy[/EN].

Documento que define permisos.

[EN]Role[/EN].

Identidad asumible que entrega permisos, normalmente temporales.

[EN]Session[/EN].

Periodo de tiempo en que una identidad asumida usa credenciales temporales.

[EN]Access key[/EN].

Credencial para acceso programático.

[MFA].

Factor adicional de autenticación.

[EN]Least privilege[/EN].

Permisos mínimos necesarios.

[EN]Federation[/EN].

Uso de una identidad externa para acceder a AWS.

[PAUSA]
900

[TEXTO]
Hablemos un poco del lenguaje de preguntas en AWS.

AWS suele premiar respuestas que sean seguras, escalables y operativamente limpias.

Por eso, si dos opciones parecen funcionar, normalmente debes buscar cuál reduce administración manual, cuál evita credenciales permanentes, cuál aplica menor privilegio y cuál sigue servicios administrados.

Este criterio te ayuda mucho cuando varias respuestas parecen técnicamente posibles.

La más alineada a buenas prácticas suele ganar.

[PAUSA]
900

[TEXTO]
Veamos algunas comparaciones rápidas muy examinables.

Usuario IAM versus rol IAM.

Usuario suele tener identidad persistente.

Rol suele asumirse para obtener acceso temporal.

Grupo IAM versus política IAM.

Grupo organiza usuarios.

Política define permisos.

MFA versus política.

MFA fortalece autenticación.

Política controla autorización.

IAM versus IAM Identity Center.

IAM da identidades y permisos base en AWS.

IAM Identity Center centraliza acceso de usuarios de la organización a múltiples cuentas y aplicaciones.

IAM versus Cognito.

IAM protege y administra acceso a recursos AWS.

Cognito gestiona autenticación de usuarios finales en aplicaciones.

[PAUSA]
900

[TEXTO]
Ahora quiero darte una estrategia concreta para estudiar IAM de cara al examen.

Paso uno.

Domina definiciones cortas y exactas.

Qué es un usuario.

Qué es un grupo.

Qué es un rol.

Qué es una política.

Qué es MFA.

Qué es menor privilegio.

Paso dos.

Practica escenarios.

Humano versus servicio.

Acceso permanente versus temporal.

Una cuenta versus múltiples cuentas.

Administración local versus centralizada.

Paso tres.

Aprende a detectar malas prácticas.

Uso diario de root.

Credenciales embebidas.

Permisos demasiado amplios.

Compartir cuentas entre varias personas.

Paso cuatro.

Relaciona IAM con servicios vecinos.

CloudTrail para auditoría.

Secrets Manager para secretos.

Organizations para gobierno multi-cuenta.

Cognito para usuarios finales.

Paso cinco.

Repasa trampas de lenguaje.

“Más seguro”, “más recomendable”, “menor esfuerzo operativo”, “acceso temporal”, “múltiples cuentas”, “usuarios corporativos”, “aplicación ejecutándose en AWS”.

Cada pista empuja a una respuesta diferente.

[PAUSA]
900

[TEXTO]
Quiero ahora simular algunas preguntas tipo examen con razonamiento breve.

Pregunta uno.

Una empresa desea que sus empleados usen sus credenciales corporativas existentes para acceder a varias cuentas AWS.

¿Cuál servicio encaja mejor?

La pista está en credenciales corporativas existentes y varias cuentas AWS.

Eso apunta a federación centralizada.

Respuesta esperada.

IAM Identity Center.

Pregunta dos.

Una instancia EC2 necesita acceder a un bucket S3 sin almacenar claves de acceso en el servidor.

La pista es sin almacenar claves.

Respuesta esperada.

Rol IAM asociado a la instancia.

Pregunta tres.

¿Cuál es la mejor práctica para la cuenta root?

Respuesta esperada.

Habilitar MFA y evitar su uso cotidiano.

Pregunta cuatro.

Un analista solo necesita ver reportes y nada más.

Respuesta esperada.

Asignar permisos de solo lectura y respetar menor privilegio.

[PAUSA]
900

[TEXTO]
Pregunta cinco.

Una empresa necesita investigar quién eliminó un recurso y cuándo ocurrió.

Aquí muchos se van directo a IAM.

Pero IAM no es el mejor servicio para auditoría histórica de acciones.

La respuesta conceptual correcta será CloudTrail.

Sin embargo, el contexto sigue ligado a identidad porque CloudTrail registra quién hizo qué.

Este tipo de preguntas mezcladas son muy típicas.

Pregunta seis.

¿Qué sucede si una política permite una acción y otra la deniega explícitamente?

Respuesta.

Gana la denegación explícita.

Pregunta siete.

¿Qué mecanismo reduce la necesidad de credenciales permanentes?

Respuesta.

Roles IAM y credenciales temporales.

[PAUSA]
900

[TEXTO]
Ahora vamos a cerrar con un resumen maestro que te puede servir como bloque de memoria antes del examen.

IAM es el servicio de AWS para controlar acceso.

Controla quién se autentica y qué puede hacer.

La cuenta root es poderosa y debe protegerse con MFA y usarse rara vez.

Los usuarios IAM son identidades tradicionales, pero AWS prefiere cada vez más roles y acceso federado para reducir credenciales permanentes.

Los grupos IAM sirven para asignar permisos a varios usuarios.

Los roles IAM se asumen y entregan credenciales temporales.

Son la respuesta favorita para servicios AWS, workloads y acceso entre cuentas.

Las políticas IAM definen permisos en JSON.

Todo empieza en denegado implícito.

Un [EN]Allow[/EN] permite.

Un [EN]Deny[/EN] explícito domina.

Menor privilegio significa dar solo lo necesario.

MFA fortalece autenticación.

IAM Identity Center centraliza acceso de usuarios corporativos a múltiples cuentas y aplicaciones.

Y la mentalidad correcta para el examen es elegir la opción más segura, más limpia operativamente y más alineada con buenas prácticas modernas de AWS.

[PAUSA]
900

[TEXTO]
Te dejo unas últimas frases de repaso rápido.

No uses root para el día a día.

No hardcodees claves.

No des permisos de más.

Usa roles cuando puedas.

Usa MFA para proteger accesos sensibles.

Piensa en Identity Center cuando haya múltiples cuentas y usuarios corporativos.

Y cuando dudes entre una opción manual y una opción administrada, segura y temporal, normalmente AWS preferirá la segunda.

[PAUSA]
900

[TEXTO]
Con esto cerramos esta guía de estudio de IAM para [EN]AWS Certified Cloud Practitioner[/EN].

Repasa este episodio varias veces.

Primero para entender.

Luego para memorizar vocabulario.

Y finalmente para identificar patrones de examen.

Cuando IAM se comprende bien, una parte importante de la sección de seguridad del examen se vuelve mucho más manejable.

Nos escuchamos en el próximo episodio.
