import { Card, CardContent, Skeleton } from "@khetibadi/ui";

export function LoadingGrid() {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      <Skeleton className="h-32" />
      <Skeleton className="h-32" />
      <Skeleton className="h-32" />
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <Card>
      <CardContent className="py-10 text-center">
        <p className="text-lg font-bold text-[#2d2217]">{title}</p>
        <p className="mt-2 text-sm text-[#7a6548]">{description}</p>
      </CardContent>
    </Card>
  );
}

export function ErrorState({ message, title }: { message: string; title: string }) {
  return (
    <Card className="border-[#d89b8b] bg-[#f4d8ce]">
      <CardContent className="text-sm text-[#8a2f22]">
        <p className="font-semibold">{title}</p>
        <p className="mt-1">{message}</p>
      </CardContent>
    </Card>
  );
}
