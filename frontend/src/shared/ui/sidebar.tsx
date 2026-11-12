import type {
  ComponentProps,
  ComponentPropsWithRef,
  CSSProperties,
} from "react";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { PanelLeft } from "lucide-react";

import { Button } from "@shared/ui/button";
import { Separator } from "@shared/ui/separator";
import { ScrollArea } from "@shared/ui/ScrollArea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@shared/ui/tooltip";
import { cn } from "@shared/utils/styling/cn";
import {
  SidebarContext,
  type SidebarContextValue,
  useSidebar,
} from "@shared/ui/sidebar-context";
import { useSidebarStore } from "@app/state/ui/sidebarStore";

export const SIDEBAR_WIDTH = "18rem";
const SIDEBAR_WIDTH_MOBILE = "18rem";

type SidebarProviderProps = ComponentPropsWithRef<"div"> & {
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
};

function SidebarProvider({
  defaultOpen = true,
  open: openProp,
  onOpenChange,
  className,
  style,
  children,
  ref,
  ...props
}: SidebarProviderProps) {
  const isOpen = useSidebarStore((state) => state.isOpen);
  const setOpen = useSidebarStore((state) => state.setOpen);
  const hasHydrated = useSidebarStore((state) => state.hasHydrated);

  useEffect(() => {
    if (openProp !== undefined) {
      setOpen(openProp);
    }
  }, [openProp, setOpen]);

  useEffect(() => {
    if (openProp === undefined && !hasHydrated) {
      setOpen(defaultOpen);
    }
  }, [defaultOpen, openProp, setOpen, hasHydrated]);

  useEffect(() => {
    onOpenChange?.(isOpen);
  }, [onOpenChange, isOpen]);

  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const state = isOpen ? "expanded" : "collapsed";
  const contextValue: SidebarContextValue = { state, isMobile };

  return (
    <SidebarContext.Provider value={contextValue}>
      <div
        style={
          {
            "--sidebar-width": SIDEBAR_WIDTH,
            "--sidebar-width-mobile": SIDEBAR_WIDTH_MOBILE,
            ...style,
          } as CSSProperties
        }
        className={cn(
          "group/sidebar-wrapper flex min-h-svh w-full has-data-[variant=inset]:bg-subtle",
          className,
        )}
        ref={ref}
        {...props}
      >
        {children}
      </div>
    </SidebarContext.Provider>
  );
}
SidebarProvider.displayName = "SidebarProvider";

type SidebarProps = ComponentPropsWithRef<"div"> & {
  side?: "left" | "right";
  variant?: "sidebar" | "floating" | "inset";
  collapsible?: "offcanvas" | "icon" | "none";
};

function Sidebar({
  side = "left",
  variant = "sidebar",
  collapsible = "offcanvas",
  className,
  children,
  style,
  ref,
  ...props
}: SidebarProps) {
  const { isMobile, state, isOpenMobile, setOpenMobile } = useSidebar();
  const location = useLocation();

  // Al navegar en mobile, el drawer debe cerrarse solo: ningun Link individual
  // (NavMain, NavSecondary, NavUser) sabe que esta dentro de un overlay.
  useEffect(() => {
    if (isMobile) {
      setOpenMobile(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  if (collapsible === "none") {
    return (
      <div
        className={cn(
          "flex h-full w-[--sidebar-width] min-w-[--sidebar-width] max-w-[--sidebar-width] flex-col bg-sidebar text-sidebar-foreground",
          "shrink-0 overflow-x-hidden",
          className,
        )}
        style={{
          width: "var(--sidebar-width)",
          minWidth: "var(--sidebar-width)",
          maxWidth: "var(--sidebar-width)",
          ...style,
        }}
        ref={ref}
        role="navigation"
        {...props}
      >
        {children}
      </div>
    );
  }

  if (isMobile) {
    return (
      <div
        className={cn(
          "fixed inset-0 z-50 bg-txt-body/50 transition-opacity",
          isOpenMobile ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={() => setOpenMobile(false)}
        aria-hidden={!isOpenMobile}
      >
        <div
          className={cn(
            "fixed inset-y-0 z-50 flex h-full w-[--sidebar-width-mobile] min-w-[--sidebar-width-mobile] max-w-[--sidebar-width-mobile] flex-col bg-sidebar text-sidebar-foreground transition-transform",
            "overflow-x-hidden",
            side === "left" ? "left-0" : "right-0",
            isOpenMobile
              ? "translate-x-0"
              : side === "left"
                ? "-translate-x-full"
                : "translate-x-full",
            className,
          )}
          style={{
            width: "var(--sidebar-width-mobile)",
            minWidth: "var(--sidebar-width-mobile)",
            maxWidth: "var(--sidebar-width-mobile)",
            ...style,
          }}
          onClick={(e) => e.stopPropagation()}
          ref={ref}
          role="navigation"
          {...props}
        >
          {children}
        </div>
      </div>
    );
  }

  return (
    <div
      ref={ref}
      className={cn(
        "fixed inset-y-0 z-40 hidden h-svh w-[--sidebar-width] min-w-[--sidebar-width] max-w-[--sidebar-width] flex-col bg-sidebar text-sidebar-foreground md:flex",
        "shrink-0 overflow-x-hidden",
        "transition-transform duration-200 ease-out motion-reduce:transition-none",
        "will-change-transform",
        side === "left"
          ? "left-0 border-r border-sidebar-border"
          : "right-0 border-l border-sidebar-border",
        state === "collapsed" &&
          (side === "left" ? "-translate-x-full" : "translate-x-full"),
        className,
      )}
      style={{
        width: "var(--sidebar-width)",
        minWidth: "var(--sidebar-width)",
        maxWidth: "var(--sidebar-width)",
        ...style,
      }}
      data-state={state}
      data-collapsible={state === "collapsed" ? collapsible : ""}
      data-variant={variant}
      data-side={side}
      role="navigation"
      {...props}
    >
      {children}
    </div>
  );
}
Sidebar.displayName = "Sidebar";

function SidebarTrigger({
  className,
  onClick,
  ref,
  ...props
}: ComponentPropsWithRef<typeof Button>) {
  const { isMobile, isOpenMobile, setOpenMobile, toggleSidebar } =
    useSidebar();

  return (
    <Button
      ref={ref}
      data-sidebar="trigger"
      variant="ghost"
      size="icon"
      className={cn("h-7 w-7", className)}
      onClick={(event) => {
        onClick?.(event);
        // En mobile el sidebar es un overlay controlado por isOpenMobile,
        // no por el estado "expanded/collapsed" de desktop (isOpen).
        if (isMobile) {
          setOpenMobile(!isOpenMobile);
        } else {
          toggleSidebar();
        }
      }}
      {...props}
    >
      <PanelLeft />
      <span className="sr-only">Toggle Sidebar</span>
    </Button>
  );
}
SidebarTrigger.displayName = "SidebarTrigger";

function SidebarHeader({
  className,
  ref,
  ...props
}: ComponentPropsWithRef<"div">) {
  return (
    <div
      ref={ref}
      data-sidebar="header"
      className={cn("flex flex-col gap-2 p-2", className)}
      {...props}
    />
  );
}
SidebarHeader.displayName = "SidebarHeader";

function SidebarFooter({
  className,
  ref,
  ...props
}: ComponentPropsWithRef<"div">) {
  return (
    <div
      ref={ref}
      data-sidebar="footer"
      className={cn("flex flex-col gap-2 p-2", className)}
      {...props}
    />
  );
}
SidebarFooter.displayName = "SidebarFooter";

function SidebarSeparator({
  className,
  ref,
  ...props
}: ComponentPropsWithRef<typeof Separator>) {
  return (
    <Separator
      ref={ref}
      data-sidebar="separator"
      className={cn("mx-2 w-auto bg-sidebar-border", className)}
      {...props}
    />
  );
}
SidebarSeparator.displayName = "SidebarSeparator";

function SidebarContent({
  className,
  children,
  ref,
  ...props
}: ComponentPropsWithRef<"div">) {
  return (
    <div
      ref={ref}
      data-sidebar="content"
      className={cn(
        "flex min-h-0 min-w-0 flex-1 flex-col gap-2 group-data-[collapsible=icon]:overflow-hidden",
        "overflow-x-hidden",
        className,
      )}
      {...props}
    >
      <ScrollArea
        tabIndex={-1}
        className="flex-1 min-w-0 px-2 focus-visible:outline-none focus-visible:ring-0"
        scrollbarClassName="w-1.5"
        viewportClassName="overscroll-contain"
      >
        <div className="flex flex-col gap-2">{children}</div>
      </ScrollArea>
    </div>
  );
}
SidebarContent.displayName = "SidebarContent";

function SidebarGroup({
  className,
  ref,
  ...props
}: ComponentPropsWithRef<"div">) {
  return (
    <div
      ref={ref}
      data-sidebar="group"
      className={cn("relative flex w-full min-w-0 flex-col px-1 py-1.5", className)}
      {...props}
    />
  );
}
SidebarGroup.displayName = "SidebarGroup";

type SidebarGroupLabelProps = ComponentPropsWithRef<"div"> & {
  asChild?: boolean;
};

function SidebarGroupLabel({
  className,
  asChild = false,
  ref,
  ...props
}: SidebarGroupLabelProps) {
  const Comp = asChild ? Slot : "div";

  return (
    <Comp
      ref={ref}
      data-sidebar="group-label"
      className={cn(
        "flex h-7 shrink-0 items-center rounded-md px-2 text-[11px] font-semibold uppercase tracking-wider text-sidebar-foreground/60 outline-none ring-line-struct/50 transition-[margin,opa] duration-200 ease-linear focus-visible:ring-4 [&>svg]:size-4 [&>svg]:shrink-0",
        "group-data-[collapsible=icon]:-mt-8 group-data-[collapsible=icon]:opacity-0",
        className,
      )}
      {...props}
    />
  );
}
SidebarGroupLabel.displayName = "SidebarGroupLabel";

function SidebarGroupContent({
  className,
  ref,
  ...props
}: ComponentPropsWithRef<"div">) {
  return (
    <div
      ref={ref}
      data-sidebar="group-content"
      className={cn("w-full text-sm", className)}
      {...props}
    />
  );
}
SidebarGroupContent.displayName = "SidebarGroupContent";

function SidebarMenu({
  className,
  ref,
  ...props
}: ComponentPropsWithRef<"ul">) {
  return (
    <ul
      ref={ref}
      data-sidebar="menu"
      className={cn("flex w-full min-w-0 flex-col gap-1", className)}
      {...props}
    />
  );
}
SidebarMenu.displayName = "SidebarMenu";

function SidebarMenuItem({
  className,
  ref,
  ...props
}: ComponentPropsWithRef<"li">) {
  return (
    <li
      ref={ref}
      data-sidebar="menu-item"
      className={cn("group/menu-item relative", className)}
      {...props}
    />
  );
}
SidebarMenuItem.displayName = "SidebarMenuItem";

const sidebarMenuButtonVariants = cva(
  "peer/menu-button relative flex w-full items-center gap-2 overflow-hidden rounded-md p-2 text-left before:absolute before:inset-y-1.5 before:left-0 before:w-0.5 before:rounded-full before:bg-sidebar-primary before:opacity-0 data-[active=true]:before:opacity-100 text-sm outline-none ring-line-struct/50 transition-all duration-150 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-4 active:bg-sidebar-accent active:text-sidebar-accent-foreground disabled:pointer-events-none disabled:opacity-50 group-has-[[data-sidebar=menu-action]]/menu-item:pr-8 aria-disabled:pointer-events-none aria-disabled:opacity-50 data-[active=true]:bg-sidebar-accent data-[active=true]:font-medium data-[active=true]:text-sidebar-accent-foreground data-[state=open]:hover:bg-sidebar-accent data-[state=open]:hover:text-sidebar-accent-foreground group-data-[collapsible=icon]:!size-8 group-data-[collapsible=icon]:!p-2 [&>span:last-child]:truncate [&>svg]:size-4 [&>svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        outline:
          "bg-sidebar border border-sidebar-border hover:bg-sidebar-accent hover:text-sidebar-accent-foreground hover:border-sidebar-accent",
      },
      size: {
        default: "min-h-8 py-1.5 text-sm",
        sm: "h-7 text-xs",
        lg: "h-12 text-sm group-data-[collapsible=icon]:!p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

type SidebarMenuButtonProps = ComponentPropsWithRef<"button"> & {
  asChild?: boolean;
  isActive?: boolean;
  tooltip?: string | ComponentProps<"div">;
} & VariantProps<typeof sidebarMenuButtonVariants>;

function SidebarMenuButton({
  asChild = false,
  isActive = false,
  variant = "default",
  size = "default",
  tooltip,
  className,
  ref,
  ...props
}: SidebarMenuButtonProps) {
  const { state, isMobile } = useSidebar();
  const Comp = asChild ? Slot : "button";
  const resolvedTooltip =
    typeof tooltip === "string"
      ? tooltip
      : typeof tooltip?.children === "string"
        ? tooltip.children
        : undefined;
  const shouldShowTooltip =
    Boolean(resolvedTooltip) && state === "collapsed" && !isMobile;

  if (!shouldShowTooltip) {
    return (
      <Comp
        ref={ref}
        data-sidebar="menu-button"
        data-size={size}
        data-active={isActive}
        className={cn(sidebarMenuButtonVariants({ variant, size }), className)}
        {...props}
      />
    );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Comp
          ref={ref}
          data-sidebar="menu-button"
          data-size={size}
          data-active={isActive}
          className={cn(
            sidebarMenuButtonVariants({ variant, size }),
            className,
          )}
          {...props}
        />
      </TooltipTrigger>
      <TooltipContent side="right" align="center">
        {resolvedTooltip}
      </TooltipContent>
    </Tooltip>
  );
}
SidebarMenuButton.displayName = "SidebarMenuButton";

function SidebarMenuSub({
  className,
  ref,
  ...props
}: ComponentPropsWithRef<"ul">) {
  return (
    <ul
      ref={ref}
      data-sidebar="menu-sub"
      className={cn(
        "flex w-full min-w-0 flex-col gap-0.5 border-l border-sidebar-border ml-3.5 pl-2 py-0.5",
        "group-data-[collapsible=icon]:hidden",
        className,
      )}
      {...props}
    />
  );
}
SidebarMenuSub.displayName = "SidebarMenuSub";

function SidebarMenuSubItem({ ref, ...props }: ComponentPropsWithRef<"li">) {
  return <li ref={ref} {...props} />;
}
SidebarMenuSubItem.displayName = "SidebarMenuSubItem";

type SidebarMenuSubButtonProps = ComponentPropsWithRef<"a"> & {
  asChild?: boolean;
  size?: "sm" | "md";
  isActive?: boolean;
};

function SidebarMenuSubButton({
  asChild = false,
  size = "md",
  isActive,
  className,
  ref,
  ...props
}: SidebarMenuSubButtonProps) {
  const Comp = asChild ? Slot : "a";

  return (
    <Comp
      ref={ref}
      data-sidebar="menu-sub-button"
      data-size={size}
      data-active={isActive}
      className={cn(
        "relative flex min-h-7 w-full min-w-0 items-center gap-2 overflow-hidden rounded-md px-2 py-1 text-sidebar-foreground before:absolute before:inset-y-1 before:left-0 before:w-0.5 before:rounded-full before:bg-sidebar-primary before:opacity-0 data-[active=true]:before:opacity-100 data-[active=true]:font-medium outline-none ring-line-struct/50 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-4 active:bg-sidebar-accent active:text-sidebar-accent-foreground disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50 [&>span:last-child]:truncate [&>svg]:size-4 [&>svg]:shrink-0 [&>svg]:text-sidebar-accent-foreground",
        "data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-accent-foreground",
        size === "sm" && "text-xs",
        size === "md" && "text-sm",
        "group-data-[collapsible=icon]:hidden",
        className,
      )}
      {...props}
    />
  );
}
SidebarMenuSubButton.displayName = "SidebarMenuSubButton";

function SidebarInset({
  className,
  style,
  ref,
  ...props
}: ComponentPropsWithRef<"main">) {
  const { state, isMobile } = useSidebar();

  return (
    <main
      ref={ref}
      style={{
        // Aplicar margen directamente con style para garantizar que funcione
        marginLeft: isMobile ? "0" : state === "expanded" ? SIDEBAR_WIDTH : "0",
        transition: "margin-left 220ms ease-out",
        ...style,
      }}
      className={cn(
        "relative flex min-h-svh min-w-0 flex-1 flex-col bg-app",
        // En mobile el margen siempre es 0
        "ml-0",
        className,
      )}
      {...props}
    />
  );
}
SidebarInset.displayName = "SidebarInset";

export {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarProvider,
  SidebarSeparator,
  SidebarTrigger,
};
