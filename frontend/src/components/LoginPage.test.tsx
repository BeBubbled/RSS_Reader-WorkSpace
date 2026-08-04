import { act, fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { LoginPage } from "./LoginPage";

test("submits supplied credentials", async () => {
  const submit = vi.fn().mockResolvedValue(undefined);
  render(<LoginPage onSubmit={submit} />);

  fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "admin" } });
  fireEvent.change(screen.getByLabelText("密码"), { target: { value: "secret" } });
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "登录" }));
  });

  expect(submit).toHaveBeenCalledWith("admin", "secret");
});
