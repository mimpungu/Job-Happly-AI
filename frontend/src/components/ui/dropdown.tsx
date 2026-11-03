import { DropdownMenu as Menu } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "@/lib/cn";

export const Dropdown = Menu.Root;
export const DropdownTrigger = Menu.Trigger;

export function DropdownContent({
  className,
  sideOffset = 6,
  ...props
}: ComponentProps<typeof Menu.Content>) {
  return (
    <Menu.Portal>
      <Menu.Content
        sideOffset={sideOffset}
        className={cn(
          "z-50 min-w-44 rounded-md border border-border bg-surface-elevated p-1 shadow-md",
          className,
        )}
        {...props}
      />
    </Menu.Portal>
  );
}

export function DropdownItem({ className, ...props }: ComponentProps<typeof Menu.Item>) {
  return (
    <Menu.Item
      className={cn(
        "flex cursor-default select-none items-center gap-2 rounded-sm px-2.5 py-2 text-sm text-foreground outline-none",
        "data-[highlighted]:bg-surface data-[disabled]:opacity-(--disabled-opacity)",
        className,
      )}
      {...props}
    />
  );
}

export function DropdownSeparator({ className, ...props }: ComponentProps<typeof Menu.Separator>) {
  return <Menu.Separator className={cn("my-1 h-px bg-border", className)} {...props} />;
}
