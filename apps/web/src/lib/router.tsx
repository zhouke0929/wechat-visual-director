import {
  AnchorHTMLAttributes,
  MouseEvent,
  ReactNode,
  useCallback,
  useEffect,
  useState,
} from "react";

const NAVIGATION_EVENT = "visual-director:navigate";

function currentPathname() {
  return window.location.pathname.replace(/\/+$/, "") || "/";
}

export function navigate(href: string) {
  const target = new URL(href, window.location.href);
  if (target.origin !== window.location.origin) {
    window.location.assign(target.href);
    return;
  }
  window.history.pushState({}, "", `${target.pathname}${target.search}${target.hash}`);
  window.dispatchEvent(new Event(NAVIGATION_EVENT));
}

export function usePathname() {
  const [pathname, setPathname] = useState(currentPathname);
  useEffect(() => {
    const update = () => setPathname(currentPathname());
    window.addEventListener("popstate", update);
    window.addEventListener(NAVIGATION_EVENT, update);
    return () => {
      window.removeEventListener("popstate", update);
      window.removeEventListener(NAVIGATION_EVENT, update);
    };
  }, []);
  return pathname;
}

export function useRouter() {
  return { push: useCallback((href: string) => navigate(href), []) };
}

export function useRouteParam(segmentBefore: string): string {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);
  const index = segments.indexOf(segmentBefore);
  return index >= 0 && segments[index + 1] ? decodeURIComponent(segments[index + 1]) : "";
}

type LinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  href: string;
  children?: ReactNode;
};

export default function Link({ href, onClick, children, ...props }: LinkProps) {
  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event);
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey ||
      props.target === "_blank" ||
      href.startsWith("#")
    ) {
      return;
    }
    event.preventDefault();
    navigate(href);
  }

  return <a href={href} onClick={handleClick} {...props}>{children}</a>;
}
