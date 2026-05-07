<?php

declare(strict_types=1);

define('BASE_PATH',   dirname(__DIR__));
define('PUBLIC_PATH', __DIR__);

require BASE_PATH . '/vendor/autoload.php';
require BASE_PATH . '/config/config.php';

use App\Core\{Router, Session};
use App\Controllers\{HomeController, AuthController, DashboardController, InvestController, AdminController, ApiController};
use App\Middleware\{AuthMiddleware, AdminMiddleware};

Session::start();

$router = new Router();

// ── Public routes ─────────────────────────────────────────────────────────────
$router->get('/',          [HomeController::class, 'index']);
$router->get('/funds',     [HomeController::class, 'funds']);
$router->get('/portfolio', [HomeController::class, 'portfolio']);
$router->get('/insights',  [HomeController::class, 'insights']);
$router->get('/about',     [HomeController::class, 'about']);
$router->post('/subscribe',[HomeController::class, 'subscribe']);

// ── Auth routes ───────────────────────────────────────────────────────────────
$router->get('/login',              [AuthController::class, 'loginForm']);
$router->post('/login',             [AuthController::class, 'login']);
$router->get('/register',           [AuthController::class, 'registerForm']);
$router->post('/register',          [AuthController::class, 'register']);
$router->get('/verify-email',       [AuthController::class, 'verifyEmail']);
$router->get('/logout',             [AuthController::class, 'logout']);
$router->post('/logout',            [AuthController::class, 'logout']);
$router->get('/forgot-password',    [AuthController::class, 'forgotPasswordForm']);
$router->post('/forgot-password',   [AuthController::class, 'forgotPassword']);
$router->get('/reset-password',     [AuthController::class, 'resetPasswordForm']);
$router->post('/reset-password',    [AuthController::class, 'resetPassword']);

// ── Dashboard routes (auth required) ─────────────────────────────────────────
$router->get('/dashboard',                          [DashboardController::class, 'index'],         [AuthMiddleware::class]);
$router->get('/dashboard/invest',                   [DashboardController::class, 'invest'],        [AuthMiddleware::class]);
$router->post('/dashboard/invest',                  [DashboardController::class, 'investPost'],    [AuthMiddleware::class]);
$router->get('/dashboard/payment/{invoice_id}',     [DashboardController::class, 'payment'],       [AuthMiddleware::class]);
$router->get('/dashboard/history',                  [DashboardController::class, 'history'],       [AuthMiddleware::class]);
$router->get('/dashboard/profile',                  [DashboardController::class, 'profile'],       [AuthMiddleware::class]);
$router->post('/dashboard/profile',                 [DashboardController::class, 'updateProfile'], [AuthMiddleware::class]);
$router->post('/dashboard/change-password',         [DashboardController::class, 'changePassword'],[AuthMiddleware::class]);
$router->post('/dashboard/withdraw',                [DashboardController::class, 'withdraw'],      [AuthMiddleware::class]);
$router->post('/dashboard/cancel-invoice',          [DashboardController::class, 'cancelInvoice'],[AuthMiddleware::class]);

// ── Payment callback (from AcceptXMR — no user auth) ──────────────────────────
$router->post('/payment/callback', [InvestController::class, 'callback']);
$router->get('/api/payment-status/{invoice_id}', [InvestController::class, 'paymentStatus']);

// ── Admin routes ─────────────────────────────────────────────────────────────
$router->get('/admin',                      [AdminController::class, 'index'],           [AuthMiddleware::class, AdminMiddleware::class]);
$router->get('/admin/users',                [AdminController::class, 'users'],           [AuthMiddleware::class, AdminMiddleware::class]);
$router->get('/admin/users/{id}',           [AdminController::class, 'viewUser'],        [AuthMiddleware::class, AdminMiddleware::class]);
$router->post('/admin/users/{id}',          [AdminController::class, 'updateUser'],      [AuthMiddleware::class, AdminMiddleware::class]);
$router->get('/admin/investments',          [AdminController::class, 'investments'],     [AuthMiddleware::class, AdminMiddleware::class]);
$router->get('/admin/plans',                [AdminController::class, 'plans'],           [AuthMiddleware::class, AdminMiddleware::class]);
$router->post('/admin/plans',               [AdminController::class, 'createPlan'],      [AuthMiddleware::class, AdminMiddleware::class]);
$router->post('/admin/plans/{id}',          [AdminController::class, 'updatePlan'],      [AuthMiddleware::class, AdminMiddleware::class]);
$router->post('/admin/plans/{id}/delete',   [AdminController::class, 'deletePlan'],      [AuthMiddleware::class, AdminMiddleware::class]);
$router->get('/admin/payouts',              [AdminController::class, 'payouts'],         [AuthMiddleware::class, AdminMiddleware::class]);
$router->post('/admin/payouts/{id}/approve',[AdminController::class, 'approvePayout'],   [AuthMiddleware::class, AdminMiddleware::class]);
$router->post('/admin/payouts/{id}/reject', [AdminController::class, 'rejectPayout'],    [AuthMiddleware::class, AdminMiddleware::class]);
$router->get('/admin/settings',             [AdminController::class, 'settings'],        [AuthMiddleware::class, AdminMiddleware::class]);
$router->post('/admin/settings',            [AdminController::class, 'updateSettings'],  [AuthMiddleware::class, AdminMiddleware::class]);
$router->get('/admin/audit-logs',           [AdminController::class, 'auditLogs'],       [AuthMiddleware::class, AdminMiddleware::class]);
$router->get('/admin/newsletter/export',    [AdminController::class, 'exportNewsletter'],[AuthMiddleware::class, AdminMiddleware::class]);

// ── API routes ────────────────────────────────────────────────────────────────
$router->get('/api/invoice/{id}', [ApiController::class, 'invoiceStatus']);
$router->get('/api/prices',       [ApiController::class, 'prices']);
$router->get('/api/stats',        [ApiController::class, 'stats']);
$router->get('/api/health',       [ApiController::class, 'health']);

$router->dispatch();
