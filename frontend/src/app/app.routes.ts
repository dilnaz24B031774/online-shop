import { inject } from '@angular/core';
import { Router, Routes } from '@angular/router';

import { authGuard } from './core/auth.guard';

export const routes: Routes = [
  { path: '', loadComponent: () => import('./pages/home.component').then(m => m.HomeComponent) },
  { path: 'catalog', loadComponent: () => import('./pages/catalog.component').then(m => m.CatalogComponent) },
  { path: 'product/:id', loadComponent: () => import('./pages/product.component').then(m => m.ProductComponent) },
  { path: 'search', loadComponent: () => import('./pages/search.component').then(m => m.SearchComponent) },
  { path: 'login', loadComponent: () => import('./pages/login.component').then(m => m.LoginComponent) },
  { path: 'forgot-password', loadComponent: () => import('./pages/forgot-password.component').then(m => m.ForgotPasswordComponent) },
  { path: 'reset-password', loadComponent: () => import('./pages/reset-password.component').then(m => m.ResetPasswordComponent) },
  { path: 'register', loadComponent: () => import('./pages/register.component').then(m => m.RegisterComponent) },
  { path: 'cart', canActivate: [authGuard], loadComponent: () => import('./pages/cart.component').then(m => m.CartComponent) },
  { path: 'checkout', canActivate: [authGuard], loadComponent: () => import('./pages/checkout.component').then(m => m.CheckoutComponent) },
  { path: 'orders/:id/tracking', canActivate: [authGuard], loadComponent: () => import('./pages/tracking.component').then(m => m.TrackingComponent) },
  { path: 'courier', loadComponent: () => import('./pages/courier.component').then(m => m.CourierComponent) },
  { path: 'bonus', canActivate: [authGuard], loadComponent: () => import('./pages/bonus.component').then(m => m.BonusComponent) },
  { path: 'support', loadComponent: () => import('./pages/support.component').then(m => m.SupportComponent) },
  { path: 'pay/:token', loadComponent: () => import('./pages/pay.component').then(m => m.PayComponent) },
  { path: 'top', loadComponent: () => import('./pages/top.component').then(m => m.TopComponent) },
  { path: 'profile', canActivate: [authGuard], loadComponent: () => import('./pages/profile.component').then(m => m.ProfileComponent) },
  // "My orders" is now a tab of the profile; old links to /orders still work
  { path: 'orders', redirectTo: () => inject(Router).parseUrl('/profile?tab=orders') },
  { path: 'settings', canActivate: [authGuard], loadComponent: () => import('./pages/settings.component').then(m => m.SettingsComponent) },
  { path: 'complaints', canActivate: [authGuard], loadComponent: () => import('./pages/complaints.component').then(m => m.ComplaintsComponent) },
  { path: '**', redirectTo: '' },
];
