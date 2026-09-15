import { useQuery } from "@tanstack/react-query";
import { Megaphone } from "lucide-react";
import { Card, CardContent } from "@shared/ui/card";
import { portalAnunciosAPI } from "@api/resources/portal.api";

export const PortalAnunciosBanner = () => {
  const { data } = useQuery({
    queryKey: ["portal", "anuncios"],
    queryFn: () => portalAnunciosAPI.getAll(),
  });

  const anuncios = [...(data?.anuncios ?? [])].sort((a, b) => a.orden - b.orden);

  if (anuncios.length === 0) return null;

  return (
    <div className="flex gap-3 overflow-x-auto pb-1 -mx-1 px-1">
      {anuncios.map((anuncio) => {
        const content = (
          <Card className="w-64 shrink-0 overflow-hidden">
            {anuncio.imagenUrl ? (
              <img
                src={anuncio.imagenUrl}
                alt={anuncio.titulo}
                className="h-28 w-full object-cover"
              />
            ) : (
              <div className="flex h-28 w-full items-center justify-center bg-primary/10">
                <Megaphone className="size-8 text-primary/60" />
              </div>
            )}
            <CardContent className="space-y-1 p-3">
              <p className="text-sm font-semibold text-txt-body">{anuncio.titulo}</p>
              {anuncio.descripcion && (
                <p className="text-xs text-txt-muted line-clamp-2">{anuncio.descripcion}</p>
              )}
            </CardContent>
          </Card>
        );

        const href = anuncio.enlaceUrl || anuncio.adjuntoUrl;
        if (!href) return <div key={anuncio.id}>{content}</div>;

        return (
          <a
            key={anuncio.id}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="block rounded-xl transition-opacity hover:opacity-90"
          >
            {content}
          </a>
        );
      })}
    </div>
  );
};

export default PortalAnunciosBanner;
