import csv
import io
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from sherlock_local.catalog import site_catalog
from sherlock_local.jobs import BusyError, JobManager

STATIC = Path(__file__).parent / "static"


class SearchRequest(BaseModel):
    username: str
    sites: list[str] = Field(default_factory=list, max_length=1000)
    timeout: int = Field(default=15, ge=3, le=60)

    @field_validator("username")
    @classmethod
    def valid_username(cls, value):
        value = value.strip()
        if not re.fullmatch(r"[\w][\w.\-]{0,63}", value, re.UNICODE):
            raise ValueError("1–64 karakter kullanın: harf, rakam, alt çizgi, nokta veya tire.")
        return value

    @field_validator("sites")
    @classmethod
    def valid_sites(cls, value):
        if any(name not in site_catalog() for name in value):
            raise ValueError("Bilinmeyen platform seçildi.")
        return list(dict.fromkeys(value))


def csv_cell(value):
    value = str(value if value is not None else "")
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value


def create_app(manager=None):
    manager = manager or JobManager()

    @asynccontextmanager
    async def lifespan(app):
        yield
        manager.close()

    app = FastAPI(title="Sherlock Local", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.method in {"POST", "DELETE", "PUT", "PATCH"}:
            origin = request.headers.get("origin")
            expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
            if (origin and origin != expected) or request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Yalnızca yerel uygulamadan gelen isteklere izin verilir."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        response.headers["Cache-Control"] = "no-store"
        return response

    def get_job(job_id):
        try:
            return manager.get(job_id)
        except KeyError:
            raise HTTPException(404, "Arama bulunamadı. Uygulama yeniden başlatılmış olabilir.")

    @app.get("/api/sites")
    def sites():
        names = sorted(site_catalog(), key=str.casefold)
        popular = [name for name in ["GitHub", "Reddit", "Instagram", "YouTube", "Pinterest", "Twitch", "Steam", "GitLab", "Medium", "Spotify"] if name in names]
        return {"sites": names, "popular": popular, "engine": "Sherlock 0.16.0"}

    @app.post("/api/searches", status_code=202)
    def start_search(body: SearchRequest):
        try:
            return manager.start(body.username, body.sites or list(site_catalog()), body.timeout)
        except BusyError as error:
            raise HTTPException(409, str(error))
        except OSError:
            raise HTTPException(503, "Arama motoru başlatılamadı. Kurulumu kontrol edin.")

    @app.get("/api/searches/{job_id}")
    def snapshot(job_id: str):
        return get_job(job_id)

    @app.delete("/api/searches/{job_id}")
    def cancel(job_id: str):
        get_job(job_id)
        return manager.cancel(job_id)

    @app.get("/api/searches/{job_id}/csv")
    def export(job_id: str):
        job = get_job(job_id)
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["Kullanıcı adı", "Platform", "Durum", "Profil URL", "Süre (sn)", "Açıklama"])
        labels = {"found": "Bulundu", "absent": "Bulunamadı", "unknown": "Kontrol edilemedi"}
        for result in job["results"]:
            writer.writerow([csv_cell(v) for v in [job["username"], result["site"], labels[result["status"]], result["url"], result.get("elapsed"), result.get("detail")]])
        return Response(output.getvalue().encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="sherlock-{job_id[:8]}.csv"'})

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    STATIC.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
