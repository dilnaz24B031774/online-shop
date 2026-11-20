import { inject } from '@angular/core';
import { Router, Routes } from '@angular/router';

import { authGuard } from './core/auth.guard';

export const routes: Routes = [
  { path: '', loadComponent: () => import('./pages/home.component').then(m => m.HomeComponent) },
  { path: 'catalog', loadComponent: () => import('./pages/catalog.component').then(m => m.CatalogComponent) },
  { path: 'product/:id', loadComponent: () => import('./pages/product.component').then(m => m.ProductComponent) },
  { path: 'search', loadComponent: () => import('./pages/search.component').then(m => m.SearchComponent) },
  { path: 'login', loadComponent: () => import('./pages/login.component').then(m => m.LoginComponent) },
  { path: 'register', loadComponent: () => import('./pages/register.component').then(m => m.RegisterComponent) },
  { path: 'cart', canActivate: [authGuard], loadComponent: () => import('./pages/cart.component').then(m => m.CartComponent) },
  { path: 'checkout', canActivate: [authGuard], loadComponent: () => import('./pages/checkout.component').then(m => m.CheckoutComponent) },
  { path: 'pay/:token', loadComponent: () => import('./pages/pay.component').then(m => m.PayComponent) },
  { path: 'top', loadComponent: () => import('./pages/top.component').then(m => m.TopComponent) },
  { path: 'profile', canActivate: [authGuard], loadComponent: () => import('./pages/profile.component').then(m => m.ProfileComponent) },
  // "My orders" is now a tab of the profile; old links to /orders still work
  { path: 'orders', redirectTo: () => inject(Router).parseUrl('/profile?tab=orders') },
  { path: '**', redirectTo: '' },
];
