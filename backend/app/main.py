from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from . import admin, auth, projects
from .config import get_settings

app = FastAPI(title='Searchroom API', version='0.1.0')
app.add_middleware(CORSMiddleware, allow_origins=[get_settings().frontend_url], allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Authorization', 'Content-Type'])
for router in (auth.router, admin.router, projects.router):
    app.include_router(router, prefix='/api/v1')


@app.exception_handler(IntegrityError)
async def conflict(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={'detail': 'This record already exists or conflicts with another change. Refresh and try again.'})


@app.middleware('http')
async def headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/api/v1/health')
def health():
    return {'status': 'ok'}
