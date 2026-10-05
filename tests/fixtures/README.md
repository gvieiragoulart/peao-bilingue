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
