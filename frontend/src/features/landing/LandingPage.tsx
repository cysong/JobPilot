import { Link } from 'react-router-dom'
import { Check, ArrowRight, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function LandingPage() {
    return (
        <div className="bg-white text-slate-900 font-sans">
            {/* Navigation */}
            <nav className="fixed w-full z-50 top-0 transition-all duration-300 bg-white/80 backdrop-blur-md border-b border-white/30">
                <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                            </svg>
                        </div>
                        <span className="font-bold text-xl text-slate-900 tracking-tight">JobPilot</span>
                    </div>
                    <div className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-600">
                        <a href="#features" className="hover:text-indigo-600 transition-colors">Features</a>
                        <a href="#how-it-works" className="hover:text-indigo-600 transition-colors">How it Works</a>
                        <a href="#pricing" className="hover:text-indigo-600 transition-colors">Pricing</a>
                    </div>
                    <div className="flex items-center gap-4">
                        <Link to="/login" className="text-sm font-medium text-slate-600 hover:text-slate-900">Log in</Link>
                        <Button asChild className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-full shadow-lg shadow-indigo-500/30">
                            <Link to="/register">Get Started Free</Link>
                        </Button>
                    </div>
                </div>
            </nav>

            {/* Hero Section */}
            <section className="pt-32 pb-20 overflow-hidden bg-[radial-gradient(circle_at_50%_50%,#eef2ff_0%,#ffffff_50%)]">
                <div className="max-w-7xl mx-auto px-6 relative">
                    <div className="text-center max-w-3xl mx-auto mb-16">
                        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 text-xs font-bold uppercase tracking-wider mb-6 border border-indigo-100">
                            <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></span>
                            New: AI Cover Letter Generator
                        </div>
                        <h1 className="text-5xl md:text-6xl font-extrabold text-slate-900 leading-tight mb-6">
                            Land Your Dream Job with <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">AI Precision</span>
                        </h1>
                        <p className="text-xl text-slate-600 mb-10 leading-relaxed">
                            Stop sending generic resumes. JobPilot automatically tailors your application to every job
                            description, increasing your interview chances by 3x.
                        </p>
                        <div className="flex flex-col sm:flex-row justify-center gap-4">
                            <Button asChild size="lg" className="h-14 px-8 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-full shadow-xl hover:shadow-2xl text-lg">
                                <Link to="/register">
                                    Start Your Free Trial
                                    <ArrowRight className="ml-2 w-5 h-5" />
                                </Link>
                            </Button>
                            <Button asChild variant="outline" size="lg" className="h-14 px-8 bg-white text-slate-700 font-bold rounded-full border-slate-200 hover:bg-slate-50 text-lg">
                                <a href="#demo">
                                    <Play className="mr-2 w-5 h-5 text-slate-400 fill-current" />
                                    Watch Demo
                                </a>
                            </Button>
                        </div>
                        <p className="mt-6 text-sm text-slate-500">No credit card required · 14-day free trial · Cancel anytime</p>
                    </div>

                    {/* Hero Image/Dashboard Mockup */}
                    <div className="relative mx-auto max-w-5xl">
                        <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-2xl blur opacity-20"></div>
                        <div className="relative bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden">
                            <img src="https://placehold.co/1200x800/f8fafc/cbd5e1?text=JobPilot+Dashboard+Preview" alt="Dashboard Preview" className="w-full h-auto opacity-90" />

                            {/* Overlay Elements */}
                            <div className="absolute top-1/4 left-10 bg-white p-4 rounded-lg shadow-lg border border-slate-100 animate-bounce duration-[3000ms]">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center text-green-600">
                                        <Check className="w-6 h-6" />
                                    </div>
                                    <div>
                                        <div className="text-sm font-bold text-slate-900">Resume Tailored!</div>
                                        <div className="text-xs text-slate-500">Match Score: 98%</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Social Proof */}
            <section className="py-10 border-y border-slate-100 bg-slate-50">
                <div className="max-w-7xl mx-auto px-6 text-center">
                    <p className="text-sm font-semibold text-slate-500 uppercase tracking-widest mb-8">Trusted by job seekers at</p>
                    <div className="flex flex-wrap justify-center gap-12 opacity-60 grayscale">
                        <span className="text-xl font-bold text-slate-400">GOOGLE</span>
                        <span className="text-xl font-bold text-slate-400">MICROSOFT</span>
                        <span className="text-xl font-bold text-slate-400">AMAZON</span>
                        <span className="text-xl font-bold text-slate-400">NETFLIX</span>
                        <span className="text-xl font-bold text-slate-400">META</span>
                    </div>
                </div>
            </section>

            {/* Features */}
            <section id="features" className="py-24 bg-white">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="text-center max-w-3xl mx-auto mb-20">
                        <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">Supercharge Your Job Hunt</h2>
                        <p className="text-lg text-slate-600">Our AI agents work 24/7 to find, analyze, and apply to jobs for you.</p>
                    </div>

                    <div className="grid md:grid-cols-3 gap-12">
                        {/* Feature 1 */}
                        <div className="group">
                            <div className="w-14 h-14 bg-blue-50 rounded-2xl flex items-center justify-center text-blue-600 mb-6 group-hover:scale-110 transition-transform">
                                <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                </svg>
                            </div>
                            <h3 className="text-xl font-bold text-slate-900 mb-3">Smart Matching</h3>
                            <p className="text-slate-600 leading-relaxed">
                                Stop wasting time on irrelevant jobs. Our AI analyzes thousands of listings to find the ones
                                that match your skills and preferences perfectly.
                            </p>
                        </div>

                        {/* Feature 2 */}
                        <div className="group">
                            <div className="w-14 h-14 bg-purple-50 rounded-2xl flex items-center justify-center text-purple-600 mb-6 group-hover:scale-110 transition-transform">
                                <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                                </svg>
                            </div>
                            <h3 className="text-xl font-bold text-slate-900 mb-3">Auto-Tailoring</h3>
                            <p className="text-slate-600 leading-relaxed">
                                We rewrite your resume and cover letter for *every single application*. Highlight the right
                                skills and keywords to pass ATS filters automatically.
                            </p>
                        </div>

                        {/* Feature 3 */}
                        <div className="group">
                            <div className="w-14 h-14 bg-green-50 rounded-2xl flex items-center justify-center text-green-600 mb-6 group-hover:scale-110 transition-transform">
                                <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                                </svg>
                            </div>
                            <h3 className="text-xl font-bold text-slate-900 mb-3">Application Tracking</h3>
                            <p className="text-slate-600 leading-relaxed">
                                Keep track of every application in one place. Our Kanban board helps you organize your job
                                search like a sales pipeline.
                            </p>
                        </div>
                    </div>
                </div>
            </section>

            {/* Footer */}
            <footer className="bg-white border-t border-slate-200 pt-16 pb-8">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="grid md:grid-cols-4 gap-12 mb-12">
                        <div className="col-span-1 md:col-span-1">
                            <div className="flex items-center gap-2 mb-4">
                                <div className="w-6 h-6 bg-indigo-600 rounded flex items-center justify-center text-white text-xs">JP</div>
                                <span className="font-bold text-lg text-slate-900">JobPilot</span>
                            </div>
                            <p className="text-sm text-slate-500">Empowering your career with artificial intelligence.</p>
                        </div>
                        <div>
                            <h4 className="font-bold text-slate-900 mb-4">Product</h4>
                            <ul className="space-y-2 text-sm text-slate-600">
                                <li><a href="#" className="hover:text-indigo-600">Features</a></li>
                                <li><a href="#" className="hover:text-indigo-600">Pricing</a></li>
                                <li><a href="#" className="hover:text-indigo-600">Success Stories</a></li>
                            </ul>
                        </div>
                        <div>
                            <h4 className="font-bold text-slate-900 mb-4">Resources</h4>
                            <ul className="space-y-2 text-sm text-slate-600">
                                <li><a href="#" className="hover:text-indigo-600">Blog</a></li>
                                <li><a href="#" className="hover:text-indigo-600">Career Guide</a></li>
                                <li><a href="#" className="hover:text-indigo-600">Help Center</a></li>
                            </ul>
                        </div>
                        <div>
                            <h4 className="font-bold text-slate-900 mb-4">Legal</h4>
                            <ul className="space-y-2 text-sm text-slate-600">
                                <li><a href="#" className="hover:text-indigo-600">Privacy</a></li>
                                <li><a href="#" className="hover:text-indigo-600">Terms</a></li>
                            </ul>
                        </div>
                    </div>
                    <div className="border-t border-slate-100 pt-8 text-center text-sm text-slate-400">
                        &copy; 2024 JobPilot Inc. All rights reserved.
                    </div>
                </div>
            </footer>
        </div>
    )
}
