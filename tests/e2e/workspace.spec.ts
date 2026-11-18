import { expect, test } from "@playwright/test";

test("calcula, filtra, exporta, invalida resultado antigo e recupera projeto", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByText("Motor local conectado", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Calcular", exact: true }).click();
  await expect(
    page.getByText("Verificações atendidas", { exact: true }),
  ).toBeVisible({ timeout: 30000 });
  await expect(page.getByText("46 de 46 verificações atendidas")).toBeVisible();
  await page.screenshot({ path: "test-results/tubstruct-01-modelo.png" });
  await page
    .locator(".view-tabs")
    .getByRole("button", { name: "Verificações", exact: true })
    .click();
  await expect(page.locator("table.checks tbody tr")).toHaveCount(46);
  await page.getByLabel("Somente não atendidas").check();
  await expect(
    page.getByText("Nenhuma verificação corresponde aos filtros."),
  ).toBeVisible();
  await page.getByLabel("Somente não atendidas").uncheck();
  await page.screenshot({ path: "test-results/tubstruct-02-verificacoes.png" });
  await page
    .locator(".view-tabs")
    .getByRole("button", { name: "Memória", exact: true })
    .click();
  await expect(
    page
      .frameLocator("iframe")
      .getByText("TubStruct 0.1.0 · OpenStruct", { exact: false }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/tubstruct-03-memoria.png" });
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Salvar", exact: true }).click();
  expect((await download).suggestedFilename()).toMatch(/\.tubstruct\.json$/);
  await page.getByLabel("Comprimento L", { exact: true }).fill("2,5");
  await page.getByLabel("Comprimento L", { exact: true }).press("Tab");
  await expect(
    page.getByText("Calcule para visualizar os resultados"),
  ).toBeVisible();
  await expect(page.getByText("46 de 46 verificações atendidas")).toHaveCount(
    0,
  );
  await page.waitForTimeout(700);
  await page.reload();
  await expect(page.getByLabel("Comprimento L", { exact: true })).toHaveValue(
    "2,5",
  );
  await expect(
    page.getByText("Pronto para analisar o tubulão", { exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("edita ações e sondagens, duplica e desfaz sem contaminar elementos", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Duplicar", exact: true }).click();
  await expect(page.locator(".tree-element")).toHaveCount(2);
  await page.getByLabel("Identificador", { exact: true }).fill("T-copia");
  await page.getByRole("button", { name: "Ações", exact: true }).click();
  await page.getByLabel("Hx · ação 2", { exact: true }).fill("8,5");
  await page
    .getByRole("button", { name: "Concluir edição", exact: true })
    .click();
  await page.getByRole("button", { name: "Ações", exact: true }).click();
  await expect(page.getByLabel("Hx · ação 2", { exact: true })).toHaveValue(
    "8,5",
  );
  await page
    .getByRole("button", { name: "Concluir edição", exact: true })
    .click();
  await page.locator(".tree-element").first().click();
  await page.getByRole("button", { name: "Ações", exact: true }).click();
  await expect(page.getByLabel("Hx · ação 2", { exact: true })).toHaveValue(
    "6",
  );
  await page
    .getByRole("button", { name: "Concluir edição", exact: true })
    .click();
  await page
    .locator(".ribbon-content")
    .getByRole("button", { name: "Sondagens", exact: true })
    .click();
  await page.getByLabel("NSPT 1", { exact: true }).fill("7");
  await page
    .getByRole("button", { name: "Concluir edição", exact: true })
    .click();
  await page.getByRole("button", { name: "Desfazer", exact: true }).click();
  await page
    .locator(".ribbon-content")
    .getByRole("button", { name: "Sondagens", exact: true })
    .click();
  await expect(page.getByLabel("NSPT 1", { exact: true })).not.toHaveValue("7");
});

test("projeto novo não inventa cargas e comunica erro de entrada", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Novo projeto", exact: true }).click();
  await page
    .getByLabel("Nome do projeto", { exact: true })
    .fill("Obra de teste");
  await page.getByRole("button", { name: "Concluir", exact: true }).click();
  await page.getByRole("button", { name: "Calcular", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("ações características");
  await expect(
    page.getByText("Verificações atendidas", { exact: true }),
  ).toHaveCount(0);
});
