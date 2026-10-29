import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

export default function Layout() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <Sidebar />
      <div className="pl-64">
        <main className="h-screen overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}