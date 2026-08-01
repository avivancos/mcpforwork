import Link from "next/link";

export function Logo({ size = 15, href = "/" }: { size?: number; href?: string }) {
  return (
    <Link href={href} className="logo" style={{ fontSize: size }}>
      <b>mcp</b>
      <span>for.work</span>
    </Link>
  );
}
