# Fixtures

HTML real do site, capturado com a sessão do usuário e **anonimizado** antes de entrar no repo.

## `profile.html`

Capturado de `https://app.vanhack.com/profile` em 2026-10-05. É o subtree `.pf-main`, com:

- **removidos:** `.dropdown-menu` (listas de opções, enormes e nunca lidas), `script`, `style`,
  `svg`, `img`, e o card do Intro Video (`.iv-player-card`, `.iv-transcript-card`, `video`) —
  o vídeo tem URL assinada com token SAS e a transcrição traz nome e história pessoal;
- **anonimizados:** nome ("Fulano De Tal"), email, telefone, código do país, validade de passaporte,
  status de visto e os links do LinkedIn/GitHub;
- **preservado:** todo o resto da estrutura e os dados profissionais (cargo, skills, experiências),
  que são o que os testes verificam.

Os valores de `input` vivem na propriedade DOM, não no atributo, então a captura copia
`value`/`checked` para atributos — sem isso a fixture abriria com todos os campos vazios.

Para recapturar depois de uma mudança no site: abra `/profile` com a sessão válida, repita esse
tratamento e **audite o arquivo** (`sig=`, `skoid`, `blob.core`, email, nome) antes de commitar.

## `listing.html`, `detail_12030.html`, `detail_12018.html`

Capturados em 2026-10-05 de `/jobs/python-jobs` (container `div.vh-cards`, depois de rolar) e de
`/job/<id>` (raiz `div.vh-jd`). Removidos `script`, `style`, `svg`, `img` e `.dropdown-menu`.
São anúncios de vaga, sem dados do usuário.

`detail_12018.html` mantém de propósito a seção `.vh-jd-recommended`, com minicards de **outras**
vagas: é o que prova que o extrator não mistura vaga recomendada com a vaga aberta.

Atenção ao escrever testes: a fixture roda sem CSS, e `inner_text()` não insere o espaço que
elementos inline teriam na página real ("CAD $160k /yr" vira "CAD$160k/yr").
