import { useLocation, Link } from 'react-router-dom'
import { Construction } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export default function PlaceholderPage() {
    const location = useLocation()

    // Format pathname to title (e.g., "/applications" -> "Applications")
    const title = location.pathname.substring(1).charAt(0).toUpperCase() + location.pathname.slice(2)

    return (
        <div className="container mx-auto max-w-4xl p-6 py-12">
            <Card className="text-center py-12">
                <CardHeader>
                    <div className="mx-auto w-16 h-16 bg-indigo-50 rounded-full flex items-center justify-center mb-4">
                        <Construction className="h-8 w-8 text-indigo-600" />
                    </div>
                    <CardTitle className="text-3xl font-bold text-slate-900">{title}</CardTitle>
                    <CardDescription className="text-lg mt-2">
                        This feature is currently under development.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <p className="text-slate-500 max-w-md mx-auto mb-8">
                        We're working hard to bring you the best AI-powered job hunting experience.
                        Check back soon for updates!
                    </p>
                    <div className="flex justify-center gap-4">
                        <Button asChild>
                            <Link to="/jobs">Browse Jobs</Link>
                        </Button>
                        <Button variant="outline" asChild>
                            <Link to="/dashboard">Return to Dashboard</Link>
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
