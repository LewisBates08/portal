import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import {
  AuthProvider,
  InvitePage,
  LoginPage,
  Protected,
  RegisterPage,
} from "./auth";
import { Dashboard, Layout, NotFound, ProjectPage } from "./pages";
import { AdminPage } from "./admin";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/invite" element={<InvitePage />} />
          <Route element={<Protected />}>
            <Route element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route
                path="projects/:projectId/:tab?"
                element={<ProjectPage />}
              />
              <Route path="admin" element={<AdminPage />} />
            </Route>
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
