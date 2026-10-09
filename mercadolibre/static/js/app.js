(function () {
  var $ = function (id) { return document.getElementById(id); };

  // --- Tarjeta: marca en vivo y formato del número
  var num = $("numero"), out = $("marca");
  var marcas = [["Mastercard", /^(5[1-5]|222[1-9]|22[3-9]\d|2[3-6]\d\d|27[01]\d|2720)/], ["Visa", /^4/],
    ["American Express", /^3[47]/], ["Cabal", /^(604|589657)/], ["Diners Club", /^(36|38|30[0-5])/]];
  if (num && out) {
    num.addEventListener("input", function () {
      var d = num.value.replace(/\D/g, "").slice(0, 19), m = "";
      marcas.forEach(function (x) { if (!m && x[1].test(d)) m = x[0]; });
      num.value = m === "American Express" ? [d.slice(0, 4), d.slice(4, 10), d.slice(10, 15)].filter(Boolean).join(" ")
                                            : d.replace(/(\d{4})(?=\d)/g, "$1 ");
      out.textContent = m || "Marca no detectada";
    });
  }

  // --- Vencimiento: agrega la "/" sola después del mes (y completa el 0 si empieza con 2-9)
  var exp = $("vencimiento");
  if (exp) {
    exp.setAttribute("maxlength", "5");
    exp.addEventListener("input", function (e) {
      var borrando = !!(e.inputType && e.inputType.indexOf("delete") === 0);
      var d = exp.value.replace(/\D/g, "");
      if (d.length === 1 && d > "1" && !borrando) d = "0" + d;
      d = d.slice(0, 4);
      exp.value = (d.length > 2 || (d.length === 2 && !borrando)) ? d.slice(0, 2) + "/" + d.slice(2) : d;
    });
  }

  // --- Crédito: mostrar cuotas solo si corresponde
  var tipo = $("tipo"), cuotas = $("cuotas");
  if (tipo && cuotas) {
    var caja = cuotas.closest("label");
    var alternar = function () { caja.classList.toggle("oculto", tipo.value !== "credito"); };
    tipo.addEventListener("change", alternar); alternar();
  }

  // --- Medidor de fuerza de contraseña (misma regla que seguridad.puntaje_clave en el servidor)
  var pw = document.querySelector("[data-medidor]"), barra = $("barra"), txt = $("fuerza");
  var comunes = ["12345678", "123456789", "1234567890", "password", "password1", "contraseña", "qwerty123", "abc12345", "11111111", "admin123", "iloveyou", "12345678a"];
  var etiquetas = ["Muy débil", "Débil", "Media", "Fuerte", "Muy fuerte"];
  function puntaje(p) {
    if (p.length < 8 || comunes.indexOf(p.toLowerCase()) >= 0 || new Set(p.split("")).size <= 2) return 0;
    var clases = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter(function (r) { return r.test(p); }).length;
    return Math.min(4, 1 + (p.length >= 12) + (clases >= 3) + (clases === 4 || p.length >= 16));
  }
  if (pw && barra) {
    pw.addEventListener("input", function () {
      var n = pw.value ? puntaje(pw.value) : -1;
      barra.setAttribute("data-nivel", n);
      txt.textContent = n < 0 ? "" : "Seguridad: " + etiquetas[n] + (n < 2 ? " (no se acepta)" : "");
    });
  }

  // --- Captcha: pedir uno nuevo
  var bc = document.querySelector("[data-captcha]"), img = $("captcha-img"), cid = $("captcha-id");
  if (bc && img && cid) bc.addEventListener("click", function () {
    fetch("/captcha/nuevo").then(function (r) { return r.json(); }).then(function (d) { if (d.img) { img.src = d.img; cid.value = d.id; } });
  });

  // --- Cupones: tocar uno de "tus cupones" lo pone en el campo
  var campoCupon = $("cupon_codigo");
  document.querySelectorAll("[data-cupon]").forEach(function (b) {
    b.addEventListener("click", function () { if (campoCupon) { campoCupon.value = b.getAttribute("data-cupon"); campoCupon.focus(); } });
  });

  // --- Entrega: mostrar la dirección solo si elige envío a domicilio
  var met = $("metodo_entrega"), bloque = $("bloque-domicilio"), aviso = $("aviso-retiro");
  if (met && bloque) {
    var alternarEntrega = function () {
      var dom = met.value === "domicilio";
      bloque.classList.toggle("oculto", !dom);
      if (aviso) aviso.classList.toggle("oculto", dom);
    };
    met.addEventListener("change", alternarEntrega); alternarEntrega();
  }

  // --- Costo de envío aproximado según el código postal
  document.querySelectorAll("[data-envio-cp]").forEach(function (inp) {
    var res = $("envio-res"), cant = $("cantidad"), btn = document.querySelector("[data-envio-btn]");
    function calcular() {
      if (!res || !inp.value.trim()) return;
      var q = cant ? cant.value : (res.getAttribute("data-cantidad") || 1);
      fetch("/api/envio?cp=" + encodeURIComponent(inp.value.trim()) + "&cantidad=" + encodeURIComponent(q))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          res.textContent = d.ok ? "Envío aprox. " + d.costo_fmt + " · " + d.zona + " (~" + d.km + " km) · " + d.dias : d.error;
        })
        .catch(function () { res.textContent = "No se pudo calcular ahora."; });
    }
    inp.addEventListener("change", calcular);
    inp.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); calcular(); } });
    if (btn) btn.addEventListener("click", calcular);
    if (inp.value) calcular();
  });

  document.querySelectorAll("[data-imprimir]").forEach(function (b) { b.addEventListener("click", function () { window.print(); }); });
})();
